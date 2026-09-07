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
# 正向用例 Prompt（只生成正常请求，预期 200）
POSITIVE_PROMPT_TEMPLATE = """
你是一名资深测试开发工程师，请根据以下接口信息生成 **3 条** 正向测试用例，只覆盖正常请求场景。

接口信息：
- 方法: {method}
- 路径: {path}
- 摘要: {summary}
- 参数: {parameters}
- 请求体: {request_body}
- 响应: {responses}

已知可用的资源 ID(请优先使用):
- pets: id = 1, 2, 3
- orders: id = 1, 2, 3
- users: username = "user1", "alice", "bob"

要求：
1. 每个测试用例必须是一个 JSON 对象,包含字段:name, method, url, headers, payload, expected_status, assertions。
2. expected_status 必须为 200。
3. 在生成 URL 时，将路径占位符（如 {petId}、{orderId}、{username}）替换为上面列出的具体值（例如宠物 ID 用 1,订单 ID 用 1,用户名用 "user1"）。
4. 请求体(payload)必须包含该接口所需的全部必填字段（请参考接口信息中的 parameters 和 requestBody,例如 name 和 photoUrls、username 和 email 等）。
5. 只输出合法的 JSON 数组，不要包含任何额外文字或注释。
"""

# 负向用例 Prompt（生成 2 条异常场景，预期 4xx）
NEGATIVE_PROMPT_TEMPLATE = """
你是一名资深测试开发工程师，请根据以下接口信息生成 **2 条** 负向测试用例，覆盖常见的参数错误场景。

接口信息：
- 方法: {method}
- 路径: {path}
- 摘要: {summary}
- 参数: {parameters}
- 请求体: {request_body}
- 响应: {responses}

已知可用的资源 ID(供参考，但负向用例应使用无效值来触发错误):
- pets: id = 1, 2, 3
- orders: id = 1, 2, 3
- users: username = "user1", "alice", "bob"

要求：
1. 每个测试用例必须是一个 JSON 对象,包含字段:name, method, url, headers, payload, expected_status, assertions。
2. expected_status 必须是 4xx(400、404、422 等)，且应与实际可能返回的错误状态码一致。
3. 生成的负向用例应只聚焦于以下一种错误场景：
   - 路径参数为负数、0 或非数字字符串(如 /pet/-1、/pet/abc)
   - 缺少必需的查询参数(如 findByStatus 不带 status)
   - 请求体缺少必填字段(如创建宠物时不提供 name 或 photoUrls)
   - 字段类型错误或非法枚举值(如 status 传 "unknown")
4. 不要使用已存在的合法 ID 作为负向用例（因为那样会返回 200,不是 4xx)。
5. 在生成 URL 时，将路径占位符替换为具体无效值（例如 petId 用 -1 或 abc,username 用空字符串）。
6. 只输出合法的 JSON 数组，不要包含任何额外文字或注释。
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

    # 清洗输出（去除可能的 markdown 代码块标记）
    cleaned = re.sub(r'```json|```', '', output_text).strip()

    # 解析 JSON
    try:
        cases = json.loads(cleaned)
    except json.JSONDecodeError:
        # 尝试提取数组部分
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
    positive_prompt = fill_prompt(POSITIVE_PROMPT_TEMPLATE, params)
    positive_cases = call_llm_and_parse(positive_prompt)

    # 生成负向用例
    negative_prompt = fill_prompt(NEGATIVE_PROMPT_TEMPLATE, params)
    negative_cases = call_llm_and_parse(negative_prompt)

    return positive_cases + negative_cases