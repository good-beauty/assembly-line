"""
generate_mock.py
从 OpenAPI/Swagger 文档自动生成 FastAPI Mock 服务路由
支持 OpenAPI 3.0 和 Swagger 2.0
"""
import json
import re
import os
import sys
from typing import Any, Dict, List

# 使脚本可同时从项目根目录或 scripts/ 目录运行
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from backend.app.services.spec_normalizer import (
    is_openapi3, get_request_body, get_response_example,
)
# 将统一结果转回 generate_mock 期望的 {required, content_type} 结构
def _required_and_ct(spec, operation):
    rb = get_request_body(spec, operation)
    return {"required": rb.get("required", []), "content_type": rb.get("content_type", "application/json")}

SPEC_PATH = os.path.join(PROJECT_ROOT, "specs", "petstore.json")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "mock_server", "main.py")


def load_spec(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_path_params(path: str) -> List[str]:
    """从路径中提取参数名，如 /pet/{petId} → ['petId']"""
    return re.findall(r"\{(\w+)\}", path)


def extract_request_body_fields(spec: Dict, operation: Dict) -> Dict:
    """提取请求体必填字段（委托规范化层，统一 Swagger2/OpenAPI3）"""
    return _required_and_ct(spec, operation)


def get_success_response(spec: Dict, operation: Dict) -> Dict:
    """提取 200 响应的示例（委托规范化层）"""
    return get_response_example(spec, operation.get("responses", {}) or {})


def generate_main(spec: Dict) -> str:
    """生成 Mock 服务的完整 Python 代码"""
    lines = []
    lines.append('"""')
    lines.append("mock_server/main.py")
    lines.append("自动生成，请勿手动修改。如需修改请编辑 scripts/generate_mock.py")
    lines.append('"""')
    lines.append("from fastapi import FastAPI, HTTPException, Query, Request")
    lines.append("from typing import Optional, List, Dict, Any")
    lines.append("")
    lines.append('app = FastAPI(title="Mock API (Generated from OpenAPI)")')
    lines.append("")
    lines.append("# ========== 预置资源（可根据需要修改） ==========")
    lines.append("PETS = {")
    lines.append("    1: {'id': 1, 'name': 'Dog', 'photoUrls': ['http://example.com/dog.jpg'], 'status': 'available'},")
    lines.append("    2: {'id': 2, 'name': 'Cat', 'photoUrls': ['http://example.com/cat.jpg'], 'status': 'pending'},")
    lines.append("    3: {'id': 3, 'name': 'Bird', 'photoUrls': ['http://example.com/bird.jpg'], 'status': 'sold'},")
    lines.append("}")
    lines.append("USERS = {")
    lines.append("    'user1': {'id': 1, 'username': 'user1', 'email': 'user1@example.com', 'password': 'pass123'},")
    lines.append("    'alice': {'id': 2, 'username': 'alice', 'email': 'alice@example.com', 'password': 'alicepass'},")
    lines.append("    'bob': {'id': 3, 'username': 'bob', 'email': 'bob@example.com', 'password': 'bobpass'},")
    lines.append("}")
    lines.append("ORDERS = {")
    lines.append("    1: {'id': 1, 'petId': 1, 'quantity': 1, 'status': 'placed', 'complete': False},")
    lines.append("    2: {'id': 2, 'petId': 2, 'quantity': 2, 'status': 'approved', 'complete': False},")
    lines.append("    3: {'id': 3, 'petId': 3, 'quantity': 1, 'status': 'delivered', 'complete': True},")
    lines.append("}")
    lines.append("")
    lines.append("def is_valid_email(email: str) -> bool:")
    lines.append('    import re')
    lines.append('    return re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$", email) is not None')
    lines.append("")

    # 遍历所有路径和方法
    paths = spec.get("paths", {})
    for path, path_item in paths.items():
        # 合并 path 级参数
        common_params = path_item.get("parameters", [])

        for method in ["get", "post", "put", "delete", "patch"]:
            if method not in path_item:
                continue

            operation = path_item[method]
            operation_id = operation.get("operationId", "")
            summary = operation.get("summary", "")

            # 生成函数名
            func_name = operation_id if operation_id else f"{method}_{path}".replace("/", "_").replace("{", "").replace("}", "").replace("-", "_").replace(".", "_")

            # 提取路径参数
            path_params = extract_path_params(path)

            # 构造 FastAPI 路径（保持原样）
            fastapi_path = path

            # 构造函数签名
            sig_parts = [f"{p}: str" for p in path_params]
            # 添加请求体参数
            has_body = False
            if is_openapi3(spec) and "requestBody" in operation:
                has_body = True
            elif not is_openapi3(spec):
                for p in operation.get("parameters", []) + common_params:
                    if p.get("in") == "body":
                        has_body = True
                        break

            if has_body:
                sig_parts.append("body: Dict[str, Any]")

            sig = ", ".join(sig_parts)

            # 生成函数
            lines.append(f"@app.{method}(\"{fastapi_path}\")")
            lines.append(f"async def {func_name}({sig}):")
            lines.append(f'    """{summary or func_name}"""')

            # 生成路径参数校验
            for p in path_params:
                lines.append(f"    # 校验 {p}")
                lines.append(f"    try:")
                lines.append(f"        int({p})")
                lines.append(f"    except (ValueError, TypeError):")
                lines.append(f"        raise HTTPException(status_code=400, detail='Invalid {p} supplied')")
                lines.append(f"    if int({p}) <= 0:")
                lines.append(f"        raise HTTPException(status_code=400, detail='Invalid {p} supplied')")

            # 生成请求体校验
            body_info = extract_request_body_fields(spec, operation)
            if body_info["required"] and has_body:
                lines.append(f"    # 校验请求体必填字段")
                required_list = body_info["required"]
                lines.append(f"    required_fields = {required_list!r}")
                lines.append(f"    if isinstance(body, dict):")
                lines.append(f"        for field in required_fields:")
                lines.append(f"            if field not in body:")
                lines.append(f"                raise HTTPException(status_code=400, detail=f'Missing required field: {{field}}')")

            # 生成基础响应（从 200 响应的示例中取）
            success_example = get_success_response(spec, operation)
            if not success_example:
                success_example = {"message": "mock success"}
            lines.append(f"    return {json.dumps(success_example, ensure_ascii=False)}")
            lines.append("")

    return "\n".join(lines)


def main():
    if not os.path.exists(SPEC_PATH):
        print(f"找不到 OpenAPI 文件: {SPEC_PATH}")
        return
    spec = load_spec(SPEC_PATH)
    code = generate_main(spec)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(code)
    print(f" 已生成: {OUTPUT_PATH}")
    print(f" 路径数: {len(spec.get('paths', {}))}")


if __name__ == "__main__":
    main()