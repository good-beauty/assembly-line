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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
SPEC_PATH = os.getenv("SPEC_PATH", os.path.join(PROJECT_ROOT, "specs", "petstore.json"))
_spec_cache = None

def load_spec():
    global _spec_cache
    if _spec_cache is None:
        with open(SPEC_PATH, "r", encoding="utf-8") as f:
            _spec_cache = json.load(f)
    return _spec_cache

def get_examples_from_spec(method: str, path: str) -> Dict:
    """从 OpenAPI 文档提取该接口的示例和约束"""
    spec = load_spec()
    paths = spec.get("paths", {})
    path_item = paths.get(path, {})
    operation = path_item.get(method.lower(), {})
    
    constraints = {
        "required_fields": [],
        "path_params": [],
        "query_params": [],
        "success_example": {},
        "error_responses": []
    }
    
    # 提取参数
    all_params = path_item.get("parameters", []) + operation.get("parameters", [])
    for p in all_params:
        pname = p.get("name")
        if p.get("in") == "path":
            constraints["path_params"].append(pname)
        elif p.get("in") == "query":
            constraints["query_params"].append(pname)
        if p.get("required"):
            constraints["required_fields"].append(pname)
    
    # 提取请求体必填字段
    rb = operation.get("requestBody", {})
    if rb:
        for ct_data in rb.get("content", {}).values():
            schema = ct_data.get("schema", {})
            if "required" in schema:
                constraints["required_fields"].extend(schema["required"])
    
    # 提取成功响应示例
    responses = operation.get("responses", {})
    for code in ["200", "201"]:
        if code in responses:
            content = responses[code].get("content", {})
            for ct_data in content.values():
                schema = ct_data.get("schema", {})
                if "example" in schema:
                    constraints["success_example"] = schema["example"]
                    break
    
    # 提取错误响应
    for code, resp in responses.items():
        if code.startswith("4"):
            constraints["error_responses"].append({
                "status": int(code),
                "description": resp.get("description", "")
            })
    
    return constraints
# ========== Prompt 模板 ==========
# 正向用例 Prompt（只生成正常请求，预期 200）
POSITIVE_PROMPT_TEMPLATE = """
你是一名资深测试开发工程师，请根据以下接口信息生成 **3 条** 正向测试用例。

接口信息：
- 方法: {method}
- 路径: {path}
- 摘要: {summary}
- 参数: {parameters}
- 请求体: {request_body}
- 响应: {responses}

硬性约束
1. 所有用例的 `expected_status` 必须是 `200`。
2. 路径参数必须替换为具体值（例如 `/pet/1`），优先使用已存在的 ID:`1`、`2`、`3`。
3. 请求体必须包含所有必填字段：`{required_fields}`。
4. 成功响应示例参考：`{success_example}`。
5. 用户相关操作只能使用：`user1`、`alice`、`bob`。
   登录凭据只能使用：
   - `user1` / `pass123`
   - `alice` / `alicepass`
   - `bob` / `bobpass`
6. `name` 字段只写简短标题（不超过 30 字），不要包含推理过程、解释或换行。
7. 只输出合法 JSON 数组，不要包含任何额外文字、注释或 Markdown 代码块。

禁止事项（违反会导致 Mock 无法匹配）
- 不要在 `PUT /pet` 后添加路径参数（正确写法：`PUT /pet`）。
- 不要在 `POST /pet` 后添加路径参数（`POST /pet/{petId}` 仅用于表单更新）。
- 不要生成以 `/user/` 结尾的 URL(username 必须非空)。
- 不要生成不存在的路由（如 `POST /pet/{petId}/someRandomPath`）。
- 不要使用 `{required_fields}` 等占位符，请求体必须含真实字段值。
- 不要把请求体嵌套在 `{"body": ...}` 中，直接传 JSON 对象或数组。
- 不要生成 `/store/inventory/{{id}}` 这类带路径参数的 URL(inventory 无路径参数)。
- 不要生成 `/user/logout/{{something}}` 这类 URL(logout 无路径参数)。
- 不要生成 trailing slash(如 `/user/user1/`)。
- 请求体缺字段时，`expected_status` 只能写 `400` 或 `422`，禁止写 `405`。
- 路径参数非法时，`expected_status` 只能写 `400`，禁止写 `405`。

输出格式
每条用例必须包含以下字段：
`name`, `method`, `url`, `headers`, `payload`, `expected_status`, `assertions`

请直接输出 JSON 数组。
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
- 可用的错误响应: {error_responses}

硬性约束
1. `expected_status` 必须是上面「可用的错误响应」中列出的状态码之一。
2. 只生成以下类型的错误用例：
   - 路径参数为非数字、负数或 `0`(如 `/pet/abc`、`/pet/-1`)
   - 缺少必填查询参数
   - 请求体缺少必填字段
3. 用户相关操作只能使用：`user1`、`alice`、`bob`。
   登录凭据只能使用：
   - `user1` / `pass123`
   - `alice` / `alicepass`
   - `bob` / `bobpass`
4. `name` 字段只写简短标题（不超过 30 字），不要包含推理过程、解释或换行。
5. 只输出合法 JSON 数组，不要包含任何额外文字、注释或 Markdown 代码块。

禁止事项(违反会导致 Mock 无法匹配)
- 不要在 `PUT /pet` 后添加路径参数（正确写法：`PUT /pet`）。
- 不要在 `POST /pet` 后添加路径参数（`POST /pet/{petId}` 仅用于表单更新）。
- 不要生成以 `/user/` 结尾的 URL(username 必须非空，例如 `/user/abc`)。
- 不要生成不存在的路由（如 `POST /pet/{petId}/someRandomPath`）。
- 不要使用 `{required_fields}` 等占位符，请求体必须含真实字段值。
- 不要把请求体嵌套在 `{"body": ...}` 中，直接传 JSON 对象或数组。
- 不要生成 `/store/inventory/{{id}}` 这类带路径参数的 URL(inventory 无路径参数)。
- 不要生成 `/user/logout/{{something}}` 这类 URL(logout 无路径参数)。
- 不要生成 trailing slash(如 `/user/user1/`)。
- 不要生成空路径（如 `/user/`）。
- 请求体缺字段时，`expected_status` 只能写 `400` 或 `422`，禁止写 `405`。
- 路径参数非法时，`expected_status` 只能写 `400`，禁止写 `405`。

输出格式
每条用例必须包含以下字段：
`name`, `method`, `url`, `headers`, `payload`, `expected_status`, `assertions`

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
                "name": case["name"][:150],
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
    constraints = get_examples_from_spec(endpoint.method, endpoint.path)
    # 构造 Prompt
    params = {
        "method": endpoint.method,
        "path": endpoint.path,
        "summary": endpoint.summary or "",
        "parameters": json.dumps(endpoint.parameters, ensure_ascii=False) if endpoint.parameters else "无",
        "request_body": json.dumps(endpoint.request_body, ensure_ascii=False) if endpoint.request_body else "无",
        "responses": json.dumps(endpoint.responses, ensure_ascii=False) if endpoint.responses else "无",
        "required_fields": json.dumps(constraints["required_fields"], ensure_ascii=False) if constraints["required_fields"] else "无",
        "success_example": json.dumps(constraints["success_example"], ensure_ascii=False) if constraints["success_example"] else "无",
        "error_responses": json.dumps(constraints["error_responses"], ensure_ascii=False) if constraints["error_responses"] else "无"
    }

    # 生成正向用例
    positive_prompt = fill_prompt(POSITIVE_PROMPT_TEMPLATE, params)
    positive_cases = call_llm_and_parse(positive_prompt)

    # 生成负向用例
    negative_prompt = fill_prompt(NEGATIVE_PROMPT_TEMPLATE, params)
    negative_cases = call_llm_and_parse(negative_prompt)

    return positive_cases + negative_cases