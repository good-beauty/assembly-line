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
from ..models import TestCase, ExecutionRecord
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')
ALLURE_CMD = r"D:\allure\allure-2.45.0\bin\allure.bat"
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
            "assertions": case.assertions  # 暂未使用
        }
        test_func = template.render(test_case=case_dict)
        test_functions.append(test_func)
    full_content = "import requests\nimport json\n\n" + "\n\n".join(test_functions)
    return full_content

def parse_junit_results(junit_xml_path):
    """解析 junit xml，返回 {case_id: status} 字典"""
    tree = ET.parse(junit_xml_path)
    root = tree.getroot()
    results = {}
    for testcase in root.iter('testcase'):
        name = testcase.get('name', '')
        # 函数名格式：test_{case_id}_{safe_name}
        parts = name.split('_')
        if len(parts) >= 2 and parts[0] == 'test' and parts[1].isdigit():
            case_id = int(parts[1])
            if testcase.find('failure') is not None:
                status = 'failed'
            elif testcase.find('error') is not None:
                status = 'error'
            elif testcase.find('skipped') is not None:
                status = 'skipped'
            else:
                status = 'passed'
            results[case_id] = status
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

        print("=== PYTEST STDOUT ===")
        print(result.stdout)
        print("=== PYTEST STDERR ===")
        print(result.stderr)

        case_status_map = parse_junit_results(junit_xml_path)
        print(f"Status map: {case_status_map}")

        records = []
        for case in cases:
            status = case_status_map.get(case.id, 'failed')
            error_message = None
            if status != 'passed':
                error_message = result.stderr[:500] if result.stderr else None
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
        try:
            cmd_str = f'"{ALLURE_CMD}" generate "{allure_results_dir}" -o "{REPORT_DIR}" --clean'
            subprocess.run(cmd_str, shell=True, check=True, capture_output=True, text=True)
        except Exception as e:
            print(f"Allure 报告生成失败: {e}")
            if hasattr(e, 'stdout'):
                print(f"STDOUT: {e.stdout}")
            if hasattr(e, 'stderr'):
                print(f"STDERR: {e.stderr}")

        status_counter = Counter(case_status_map.values())
        summary = {
            "total": len(cases),
            "passed": status_counter.get('passed', 0),
            "failed": status_counter.get('failed', 0),
            "error": status_counter.get('error', 0),
            "skipped": status_counter.get('skipped', 0),
            "records": [r.id for r in records]
        }
        return summary