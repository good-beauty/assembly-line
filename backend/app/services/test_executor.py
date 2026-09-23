import subprocess
import re
import os
import json
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader
from typing import List, Dict
from pathlib import Path
from ..models import TestCase, ExecutionRecord
from dotenv import load_dotenv
from ..logging_config import get_logger

logger = get_logger("test_executor")

# 统一从项目根目录加载 .env（而非当前工作目录），保证 ALLURE_CMD 等取到
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # backend/app/services/test_executor.py -> 项目根
load_dotenv(_PROJECT_ROOT / ".env")

IN_DOCKER = os.getenv("IN_DOCKER", "false").lower() == "true"
BASE_URL = "http://mock:5000" if IN_DOCKER else "http://localhost:5000"
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')
# Allure 命令从环境变量读取，避免硬编码本机绝对路径
ALLURE_CMD = os.getenv("ALLURE_CMD", "allure")
ALLURE_RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'allure-results')
REPORT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'allure-report')

def sanitize_name(name: str) -> str:
    """将中文或特殊字符转换为安全的函数名"""
    safe = re.sub(r'\W+', '_', name)
    if safe and safe[0].isdigit():
        safe = '_' + safe
    return safe

def to_python_literal(obj):
    """将 JSON 对象转换为 Python 字面量字符串，处理 null/true/false 等"""
    if obj is None:
        return 'None'
    if isinstance(obj, bool):
        return 'True' if obj else 'False'
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, str):
        return repr(obj)
    if isinstance(obj, list):
        return '[' + ', '.join(to_python_literal(item) for item in obj) + ']'
    if isinstance(obj, dict):
        items = []
        for k, v in obj.items():
            items.append(f'{to_python_literal(k)}: {to_python_literal(v)}')
        return '{' + ', '.join(items) + '}'
    # 其他情况回退到 repr
    return repr(obj)

def render_assertions(assertions) -> list:
    """将 LLM 生成的断言转成安全、受控的 Python 断言行，避免代码注入与语法错误。

    支持的断言格式（dict）：
      - {"contains": "text"}          响应响应体包含指定文本
      - {"field_exists": "petId"}     响应 JSON 中存在该字段
      - {"field_equals": ["petId", 1]}响应 JSON 中指定字段值等于某值
    其余格式一律忽略。
    """
    lines = []
    if not isinstance(assertions, list):
        return lines
    for a in assertions:
        if not isinstance(a, dict):
            continue
        if isinstance(a.get("contains"), str):
            text = to_python_literal(a["contains"])
            lines.append(f"assert {text} in response.text")
        elif isinstance(a.get("field_exists"), str):
            field = to_python_literal(a["field_exists"])
            lines.append(f"assert {field} in response.json(), 'missing field {field}'")
        elif (isinstance(a.get("field_equals"), list)
              and len(a["field_equals"]) == 2):
            field, expect = a["field_equals"]
            lines.append(f"assert response.json().get({to_python_literal(field)}) == {to_python_literal(expect)}")
    return lines

def render_pytest_file(test_cases):
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template('pytest_template.j2')
    test_functions = []
    for case in test_cases:
        url = case.url
        if not url.startswith("http"):
            url = BASE_URL.rstrip("/") + "/" + url.lstrip("/")
        safe_name = sanitize_name(case.name)
        # 将 case.id 加入函数名，确保唯一且可解析
        function_name = f"{case.id}_{safe_name}"
        # 将 headers 和 payload 转换为 Python 字面量
        headers_literal = to_python_literal(case.headers) if case.headers is not None else '{}'
        payload_literal = to_python_literal(case.payload) if case.payload is not None else '{}'
        case_dict = {
            "name": function_name,
            "method": case.method,
            "url": url,
            "headers": headers_literal,
            "payload": payload_literal,
            "expected_status": case.expected_status,
            "assertion_lines": render_assertions(case.assertions)
        }
        test_func = template.render(test_case=case_dict)
        test_functions.append(test_func)
    reset_url = BASE_URL.rstrip("/") + "/__reset__"
    # 每条用例执行前重置 Mock 预置状态，实现用例级隔离，
    # 避免任一用例修改共享状态（如删除/创建资源）影响后续用例的判断
    fixture_header = (
        "import requests\n"
        "import json\n"
        "import pytest\n\n"
        "@pytest.fixture(autouse=True)\n"
        "def _isolate_test_state():\n"
        "    try:\n"
        f"        requests.post({to_python_literal(reset_url)}, json={{}}, timeout=10)\n"
        "    except Exception:\n"
        "        pass\n\n"
    )
    full_content = fixture_header + "\n\n".join(test_functions)
    return full_content

def parse_junit_results(junit_xml_path):
    """解析 junit xml，返回 {case_id: (status, error_message)} 字典"""
    tree = ET.parse(junit_xml_path)
    root = tree.getroot()
    results = {}
    for testcase in root.iter('testcase'):
        name = testcase.get('name', '')
        # 函数名格式：test_{case_id}_{safe_name}
        parts = name.split('_')
        if len(parts) >= 2 and parts[0] == 'test' and parts[1].isdigit():
            case_id = int(parts[1])
            failure = testcase.find('failure')
            error = testcase.find('error')
            if failure is not None:
                status = 'failed'
                message = (failure.get('message') or (failure.text or '').strip())[:500]
            elif error is not None:
                status = 'error'
                message = (error.get('message') or (error.text or '').strip())[:500]
            elif testcase.find('skipped') is not None:
                status = 'skipped'
                message = None
            else:
                status = 'passed'
                message = None
            results[case_id] = (status, message)
    return results

def execute_tests(db: Session, test_case_ids=None):
    query = db.query(TestCase)
    if test_case_ids:
        query = query.filter(TestCase.id.in_(test_case_ids))
    cases = query.all()
    if not cases:
        return {"total": 0, "passed": 0, "failed": 0, "error": 0, "records": []}

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file_path = os.path.join(tmpdir, 'test_generated.py')
        content = render_pytest_file(cases)
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        allure_results_dir = ALLURE_RESULTS_DIR
        os.makedirs(allure_results_dir, exist_ok=True)
        for filename in os.listdir(allure_results_dir):
            file_path = os.path.join(allure_results_dir, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

        junit_xml_path = os.path.join(tmpdir, 'junit.xml')
        cmd = [
            'pytest', test_file_path,
            '--alluredir', allure_results_dir,
            '--junitxml', junit_xml_path,
            '-v'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=tmpdir)

        logger.debug("=== PYTEST STDOUT ===\n%s", result.stdout)
        logger.debug("=== PYTEST STDERR ===\n%s", result.stderr)

        case_status_map = parse_junit_results(junit_xml_path)
        logger.debug("Status map: %s", case_status_map)

        records = []
        for case in cases:
            status, error_message = case_status_map.get(case.id, ('failed', None))
            record = ExecutionRecord(
                test_case_id=case.id,
                status=status,
                duration="unknown",
                error_message=error_message,
                executed_at=datetime.utcnow()
            )
            db.add(record)
            records.append(record)
        db.commit()

        os.makedirs(REPORT_DIR, exist_ok=True)
        # 使用参数列表而非 shell=True，避免命令注入风险
        try:
            result_allure = subprocess.run(
                [ALLURE_CMD, "generate", allure_results_dir, "-o", REPORT_DIR, "--clean"],
                check=True, capture_output=True, text=True
            )
        except subprocess.CalledProcessError as e:
            logger.warning("Allure 报告生成失败: %s", e)
            logger.debug("Allure STDOUT: %s", e.stdout)
            logger.debug("Allure STDERR: %s", e.stderr)
        except Exception as e:
            logger.error("Allure 报告生成失败: %s", e)

        status_counter = Counter(status for status, _ in case_status_map.values())
        summary = {
            "total": len(cases),
            "passed": status_counter.get('passed', 0),
            "failed": status_counter.get('failed', 0),
            "error": status_counter.get('error', 0),
            "skipped": status_counter.get('skipped', 0),
            "records": [r.id for r in records]
        }
        return summary