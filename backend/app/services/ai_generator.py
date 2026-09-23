import json
import re
import os
import dashscope
from dashscope import Generation
from typing import List, Dict
from dotenv import load_dotenv
from ..logging_config import get_logger

logger = get_logger("ai_generator")
load_dotenv()  # 加载 .env 文件中的环境变量

# 设置 DashScope API Key（启动时校验，避免运行期才报错）
LLM_API_KEY = os.getenv("LLM_API_KEY")
if not LLM_API_KEY:
    raise RuntimeError("未配置 LLM_API_KEY 环境变量，请在 .env 或 docker-compose 中设置")
dashscope.api_key = LLM_API_KEY
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
    """从 OpenAPI 文档提取该接口的示例和约束（统一 Swagger2/OpenAPI3）"""
    from .spec_normalizer import get_parameters, get_request_body, \
        get_response_example, get_error_codes

    spec = load_spec()
    path_item = spec.get("paths", {}).get(path, {})
    operation = path_item.get(method.lower(), {})

    constraints = {
        "required_fields": [],
        "path_params": [],
        "query_params": [],
        "success_example": {},
        "error_responses": []
    }

    # 提取参数（path 级 + operation 级，已去掉 body 参数）
    all_params = get_parameters(spec, path_item, operation)
    for p in all_params:
        pname = p.get("name")
        if p.get("in") == "path":
            constraints["path_params"].append(pname)
        elif p.get("in") == "query":
            constraints["query_params"].append(pname)
        if p.get("required"):
            constraints["required_fields"].append(pname)

    # 提取请求体必填字段（统一处理两种规范的 body/requestBody）
    rb = get_request_body(spec, operation)
    constraints["required_fields"].extend(rb.get("required", []))

    # 提取成功响应示例
    constraints["success_example"] = get_response_example(spec, operation.get("responses", {}))

    # 提取错误响应
    responses = operation.get("responses", {}) or {}
    for code in get_error_codes(spec, responses):
        resp = responses.get(str(code), {}) or {}
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
6. 登录与用户类请求，且只能【逐字】使用以下三组凭证（不要改写、不要换密码）：
   - `user1` / `pass123`
   - `alice` / `alicepass`
   - `bob` / `bobpass`
7. Pet 的请求体必须包含 `name`（字符串）和 `photoUrls`（字符串数组，如 `["http://example.com/1.jpg"]`）两个必填字段；覆盖 `PUT /pet` 时同样必须带齐这两项。
8. `name` 字段只写简短标题（不超过 30 字），不要包含推理过程、解释或换行。
9. 只输出合法 JSON 数组，不要包含任何额外文字、注释或 Markdown 代码块。

禁止事项（违反会导致 Mock 无法匹配）
- 不要在 `PUT /pet` 后添加路径参数（正确写法：`PUT /pet`）。
- 不要在 `POST /pet` 后添加路径参数（`POST /pet/{petId}` 仅用于表单更新）。
- 不要生成以 `/user/` 结尾的 URL(username 必须非空)。
- 不要生成不存在的路由（如 `POST /pet/{petId}/someRandomPath`）。
- 不要使用 `{required_fields}` 等占位符，请求体必须含真实字段值。
- 不要把请求体嵌套在 `{"body": ...}` 中，直接传 JSON 对象或数组。
- 不要生成 `/store/inventory/{{id}}` 这类带路径参数的 URL(inventory 无路径参数)。
- 不要生成 `/user/logout/{{something}}` 这类 URL(logout 无路径参数)。
- 不要生成 trailing slash(如 `/user/user1/`)、空用户名(如 `/user/`)或多余路径段。
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
2. 只生成真实可复现的错误场景（否则会因状态码不匹配而失败）。请先根据「参数/路径/请求体」判断该接口的结构，再选择下列场景：
   a) 缺必填字段：仅当某字段在必填列表 `{required_fields}` 中出现时，才生成「缺少该字段」用例，`expected_status` 写 `400` 或 `422`。若某字段不在必填列表，绝不要生成缺它的用例。
   b) 非法/越界路径参数：仅当该接口【确实存在路径参数】时才生成，如 `/pet/abc`、`/pet/-1`、`/user/user@x`，`expected_status` 写 `400`。若接口【没有路径参数】，切勿在 URL 末尾追加多余路径段（会返回 404 而非 400）；此时请改而生成「缺少必填查询参数」或「非法查询参数」用例。
3. 用户与 404 语义（重要，避免状态码错配）：
   - username 格式非法（含 `@`、空格、或为空串）→ `400`。
   - username 格式合法但该用户不存在（不要用 `user1`/`alice`/`bob`，如用 `ghost`）→ `404`。
   - petId/orderId 不存在、超出范围 → `404`（已存在的 id 为 1、2、3）。
   - 不要对「不存在的用户/资源」期望 `400`。
4. 用户相关操作只能使用：`user1`、`alice`、`bob`，且登录/用户凭证【逐字】使用：
   - `user1` / `pass123`
   - `alice` / `alicepass`
   - `bob` / `bobpass`
5. `name` 字段只写简短标题（不超过 30 字），不要包含推理过程、解释或换行。
6. 只输出合法 JSON 数组，不要包含任何额外文字、注释或 Markdown 代码块。

禁止事项(违反会导致 Mock 无法匹配)
- 不要在 `PUT /pet` 后添加路径参数（正确写法：`PUT /pet`）。
- 不要在 `POST /pet` 后添加路径参数（`POST /pet/{petId}` 仅用于表单更新）。
- 不要生成以 `/user/` 结尾的 URL(username 必须非空，例如 `/user/abc`)。
- 不要生成不存在的路由（如 `POST /pet/{petId}/someRandomPath`）。
- 不要使用 `{required_fields}` 等占位符，请求体必须含真实字段值。
- 不要把请求体嵌套在 `{"body": ...}` 中，直接传 JSON 对象或数组。
- 不要生成 `/store/inventory/{{id}}` 这类带路径参数的 URL(inventory 无路径参数)。
- 不要生成 `/user/logout/{{something}}` 这类 URL(logout 无路径参数)。
- 不要生成 trailing slash(如 `/user/user1/`)或空路径(如 `/user/`)。
- 不要在无路径参数的接口 URL 上追加任何额外路径段（否则 404）。
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

def _normalize_generated_cases(cases: List[Dict]) -> List[Dict]:
    """对齐 LLM 生成的用例预期与实际 Mock 行为（确定性规则）。

    不放松 Mock 校验（避免通过率虚高），而是修正/丢弃 LLM 生成的、
    预期状态码与真实接口行为不匹配的用例：
      1. 以 `/` 结尾的畸形路径（如 `GET /user/` 空用户名）不会被路由到 400
         处理器，FastAPI 实际返回 404 或 405，直接丢弃以免虚假失败。
      2. 空值过滤查询（如 `?tags=`、`?status=`）在 Mock 中被判定为非法，
         expected_status 应修正为 400。
      3. 空数组请求体（如 `POST /user/createWithList` 传 `[]`）在 Mock 中
         被判为非空校验失败，expected_status 应修正为 400。
    """
    normalized = []
    for c in cases:
        url = c.get("url", "")
        expected = int(c.get("expected_status", 200))
        if url.endswith("/"):
            logger.info("丢弃畸形路径用例（预期与路由行为不匹配）: method=%s url=%s",
                        c.get("method"), url)
            continue
        # logout 携带任何查询参数都会被 Mock 判为 400（其从不返回 404/405）
        if "/user/logout?" in url and expected in (404, 405):
            logger.info("修正 logout 查询参数预期 %s->400: url=%s", expected, url)
            c["expected_status"] = 400
        if expected in (200, 201, 204, 300):
            if re.search(r"\?(tags|status)=\s*$", url, re.IGNORECASE):
                logger.info("修正空值过滤查询预期 %s->400: url=%s", expected, url)
                c["expected_status"] = 400
            elif isinstance(c.get("payload"), list) and len(c["payload"]) == 0:
                logger.info("修正空数组请求体预期 %s->400: url=%s", expected, url)
                c["expected_status"] = 400
        normalized.append(c)
    return normalized

def generate_cases_for_dataset(method, path, summary, parameters, request_body, responses) -> List[Dict]:
    """调用大模型，为单个接口生成测试用例（纯数据版本，线程安全）"""
    constraints = get_examples_from_spec(method, path)
    # 构造 Prompt
    params = {
        "method": method,
        "path": path,
        "summary": summary or "",
        "parameters": json.dumps(parameters, ensure_ascii=False) if parameters else "无",
        "request_body": json.dumps(request_body, ensure_ascii=False) if request_body else "无",
        "responses": json.dumps(responses, ensure_ascii=False) if responses else "无",
        "required_fields": json.dumps(constraints["required_fields"], ensure_ascii=False) if constraints["required_fields"] else "无",
        "success_example": json.dumps(constraints["success_example"], ensure_ascii=False) if constraints["success_example"] else "无",
        "error_responses": json.dumps(constraints["error_responses"], ensure_ascii=False) if constraints["error_responses"] else "无"
    }

    # 生成正向用例
    positive_prompt = fill_prompt(POSITIVE_PROMPT_TEMPLATE, params)
    positive_cases = _normalize_generated_cases(call_llm_and_parse(positive_prompt))

    # 生成负向用例
    negative_prompt = fill_prompt(NEGATIVE_PROMPT_TEMPLATE, params)
    negative_cases = _normalize_generated_cases(call_llm_and_parse(negative_prompt))

    return positive_cases + negative_cases


def generate_cases_for_endpoint(endpoint) -> List[Dict]:
    """调用大模型，为单个接口生成测试用例（ORM 对象包装，供路由调用）"""
    return generate_cases_for_dataset(
        endpoint.method, endpoint.path, endpoint.summary,
        endpoint.parameters, endpoint.request_body, endpoint.responses
    )

def generate_cases_for_endpoints_batch(endpoints, max_workers: int = 4) -> Dict[int, List[Dict]]:
    """并发为多个接口生成测试用例，返回 {endpoint_id: cases}。

    参数要求 endpoints 为可迭代对象，元素为类的实例（mock 出 method/path/
    summary/parameters/request_body/responses 属性）。单个接口失败不影响其他接口。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _worker(ep):
        try:
            cases = generate_cases_for_dataset(
                ep.method, ep.path, ep.summary,
                ep.parameters, ep.request_body, ep.responses
            )
            return ep.id, cases
        except Exception as e:
            logger.warning("接口 '%s' 生成失败: %s", getattr(ep, 'name', ep.id), e)
            return ep.id, []

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, ep): ep.id for ep in endpoints}
        for future in as_completed(futures):
            ep_id, cases = future.result()
            results[ep_id] = cases
    return results