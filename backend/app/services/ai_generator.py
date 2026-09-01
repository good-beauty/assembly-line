import json
import re
import os
import dashscope
from dashscope import Generation
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件中的环境变量

# 设置 DashScope API Key
dashscope.api_key = os.getenv("LLM_API_KEY")
MODEL_NAME = os.getenv("LLM_MODEL", "qwen-plus")

# ========== Prompt 模板 ==========
PROMPT_TEMPLATE = """
你是一名资深测试开发工程师，擅长根据接口定义设计全面的测试用例。

请根据以下接口信息，生成 **3 条** 测试用例，覆盖正常场景和常见异常场景（如参数缺失、非法值、边界值等）。

接口信息：
- 方法: {method}
- 路径: {path}
- 摘要: {summary}
- 参数: {parameters}
- 请求体: {request_body}
- 响应: {responses}

要求：
1. 每个测试用例必须是一个 JSON 对象，包含以下字段：
   - "name": 测试用例名称（简短描述测试场景）
   - "method": HTTP 方法（如 GET、POST 等）
   - "url": 请求 URL(路径中的占位符如 {{petId}} 保留，可替换为具体值)
   - "headers": 请求头 JSON 对象(如 {{"Content-Type": "application/json"}})
   - "payload": 请求体 JSON 对象(GET 请求可为空 {{}})
   - "expected_status": 预期 HTTP 状态码（整数）
   - "assertions": 断言列表，每个断言是一个 JSON 对象，包含 "type"（如 "jsonpath", "contains", "equals"）和 "value"（期望值或表达式）
2. 所有输出必须是一个合法的 JSON 数组，不要包含任何额外文字或注释。
3. 确保 JSON 格式正确，可以被 Python 的 json.loads 解析。
4、只生成正常请求的测试用例,所有测试用例的预期状态码必须是 200。请勿生成异常场景(如参数缺失、非法值)。
5、在生成 URL 时，请将路径中的占位符（如 {petId}、{orderId}、{username} 等）替换为具体的示例值（例如数字 1 或字符串 "test"）。不要保留花括号。
请直接输出 JSON 数组。
"""

NEGATIVE_PROMPT_TEMPLATE = """
你是一名资深测试开发工程师，擅长根据接口定义设计全面的测试用例。
请根据以下接口信息，生成 **2 条** 负向测试用例，覆盖常见的异常场景，例如参数缺失、非法值、边界值等。

接口信息：
- 方法: {method}
- 路径: {path}
- 摘要: {summary}
- 参数: {parameters}
- 请求体: {request_body}
- 响应: {responses}

要求：
1. 每个测试用例必须是一个 JSON 对象，包含以下字段：
   - "name": 测试用例名称（简短描述异常场景）
   - "method": HTTP 方法
   - "url": 请求 URL(路径参数用具体值替换，(可使用无效值)
   - "headers": 请求头 JSON 对象
   - "payload": 请求体 JSON 对象
   - "expected_status": 预期 HTTP 状态码（必须是 4xx,例如 400、404、422 等）
   - "assertions": 断言列表（可包含错误信息检查）
2. 所有输出必须是一个合法的 JSON 数组，不要包含任何额外文字或注释。
3. 预期状态码必须与实际可能返回的 4xx 状态码一致。
4、确保 JSON 格式正确，可以被 Python 的 json.loads 解析。
5、在生成 URL 时，请将路径中的占位符（如 {petId}、{orderId}、{username} 等）替换为具体的示例值（例如数字 1 或字符串 "test"）。不要保留花括号。
请直接输出 JSON 数组。
"""
def fill_prompt(template: str, params: Dict) -> str:
    """安全地替换模板中的占位符，避免花括号冲突"""
    for key, value in params.items():
        template = template.replace("{" + key + "}", str(value))
    return template

def call_llm_and_parse(prompt: str) -> List[Dict]:
    """调用大模型并解析返回的 JSON 数组"""
    response = Generation.call(
        model=MODEL_NAME,
        prompt=prompt,
        result_format='message',
        max_tokens=2000,
        temperature=0.2,
    )
    if response.status_code == 200:
        output_text = response.output.choices[0].message.content
    else:
        raise Exception(f"DashScope 调用失败: {response.code} - {response.message}")

    cleaned = re.sub(r'```json|```', '', output_text).strip()
    try:
        cases = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', cleaned, re.DOTALL)
        if match:
            cases = json.loads(match.group(0))
        else:
            raise Exception("无法解析模型输出为 JSON 数组")

    valid_cases = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        if all(k in case for k in ["name", "method", "url", "expected_status"]):
            valid_cases.append({
                "name": case["name"],
                "method": case.get("method"),
                "url": case.get("url"),
                "headers": case.get("headers", {}),
                "payload": case.get("payload", {}),
                "expected_status": int(case.get("expected_status", 200)),
                "assertions": case.get("assertions", []),
                "model_used": MODEL_NAME
            })
    return valid_cases

def generate_cases_for_endpoint(endpoint) -> List[Dict]:
    """调用大模型，为单个接口生成测试用例"""
    # 构造 Prompt
    params = {
        "method": endpoint.method,
        "path": endpoint.path,
        "summary": endpoint.summary or "",
        "parameters": json.dumps(endpoint.parameters, ensure_ascii=False) if endpoint.parameters else "无",
        "request_body": json.dumps(endpoint.request_body, ensure_ascii=False) if endpoint.request_body else "无",
        "responses": json.dumps(endpoint.responses, ensure_ascii=False) if endpoint.responses else "无"
    }

    # 生成正向用例
    positive_prompt = fill_prompt(PROMPT_TEMPLATE, params)
    positive_cases = call_llm_and_parse(positive_prompt)

    # 生成负向用例
    negative_prompt = fill_prompt(NEGATIVE_PROMPT_TEMPLATE, params)
    negative_cases = call_llm_and_parse(negative_prompt)

    return positive_cases + negative_cases