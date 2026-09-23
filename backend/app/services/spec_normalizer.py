# -*- coding: utf-8 -*-
"""spec_normalizer.py
统一 Swagger 2.0 与 OpenAPI 3.0 的解析层，向上层屏蔽两种规范的字段差异：

- 请求体规范差异
  - Swagger 2.0: operation.parameters 中 `in == "body"` 的元素，schema 在其 `.schema`
  - OpenAPI 3: operation.requestBody.content[content_type].schema
- 响应规范差异
  - Swagger 2.0: responses[code].schema
  - OpenAPI 3: responses[code].content[content_type].schema
- 参数/必填字段差异：两者参数均带 `in` 与 `required`，逻辑一致
"""
from typing import Dict, Any, Optional, Tuple, List


def detect_version(spec: Dict) -> str:
    """返回 'swagger2' 或 'openapi3'。"""
    if "openapi" in spec:
        return "openapi3"
    return "swagger2"


def is_openapi3(spec: Dict) -> bool:
    return detect_version(spec) == "openapi3"


def resolve_ref(spec: Dict, ref: str) -> Optional[Dict]:
    """解析 $ref（支持 /definitions/ 与 /components/ 两种安全路径）。"""
    if not ref or not isinstance(ref, str):
        return None
    parts = [p for p in ref.lstrip("/").split("/") if p]
    if not parts:
        return None
    key = parts[-1]
    if is_openapi3(spec):
        return spec.get("components", {}).get("schemas", {}).get(key)
    return spec.get("definitions", {}).get(key)


def _expand_schema(spec: Dict, schema: Optional[Dict], seen: Optional[set] = None) -> Dict:
    """展开 schema 中的 $ref（保留原始结构，返回浅拷贝，避免循环引用陷入死循环）。"""
    if not isinstance(schema, dict):
        return schema or {}
    if "$ref" in schema:
        resolved = resolve_ref(spec, schema["$ref"])
        if not resolved:
            return schema
        seen = seen or set()
        ref_key = schema["$ref"]
        if ref_key in seen:
            return {"type": "object", "properties": schema}
        seen.add(ref_key)
        copy = dict(resolved)
        for k, v in resolved.items():
            if k in ("properties",) and isinstance(v, dict):
                copy[k] = {pk: _expand_schema(spec, pv, seen) for pk, pv in v.items()}
        return copy
    return schema


def get_parameters(spec: Dict, path_item: Dict, operation: Dict) -> List[Dict]:
    """合并 path 级与 operation 级参数，返回参数列表（含 name/in/required/type）。"""
    path_params = path_item.get("parameters", []) or []
    op_params = operation.get("parameters", []) or []
    combined = list(path_params) + list(op_params)
    # 排除请求体参数（Swagger2 的 in:body），统一由 get_request_body 处理
    return [p for p in combined if p.get("in", "") != "body"]


def get_request_body(spec: Dict, operation: Dict) -> Dict:
    """返回统一请求体信息 {"content_type": str, "required": [..], "schema": {...}}。"""
    if is_openapi3(spec):
        rb = operation.get("requestBody", {}) or {}
        content = rb.get("content", {}) or {}
        for ct, ct_data in content.items():
            schema = ct_data.get("schema", {})
            expanded = _expand_schema(spec, schema)
            return {
                "content_type": ct,
                "required": expanded.get("required", []),
                "schema": expanded,
                "example": expanded.get("example", {}),
            }
        return {"content_type": "", "required": [], "schema": {}, "example": {}}
    # Swagger 2.0
    for p in operation.get("parameters", []) or []:
        if p.get("in") == "body":
            schema = _expand_schema(spec, p.get("schema", {}))
            return {
                "content_type": "application/json",
                "required": schema.get("required", []),
                "schema": schema,
                "example": schema.get("example", {}),
            }
    return {"content_type": "", "required": [], "schema": {}, "example": {}}


def get_response_example(spec: Dict, responses: Dict) -> Dict:
    """优先返回 200/201 响应示例（已展开 $ref），取不到则返回 {}。"""
    for code in ("200", "201"):
        resp = responses.get(code)
        if not resp:
            continue
        schema = None
        if is_openapi3(spec):
            content = resp.get("content", {}) or {}
            for ct_data in content.values():
                schema = ct_data.get("schema", {})
                if schema:
                    break
        else:
            schema = resp.get("schema", {})
        expanded = _expand_schema(spec, schema)
        if expanded.get("example"):
            return expanded["example"]
        # 无显式 example 时，从 properties 构造一个含全部键的空示例（便于 LLM 引用字段名）
        props = expanded.get("properties", {})
        if props:
            return {k: None for k in props}
    return {}


def get_error_codes(spec: Dict, responses: Dict) -> List[int]:
    """返回 4xx 状态码列表（用于负向用例约束）。"""
    codes = []
    for code, resp in responses.items():
        if isinstance(code, str) and code.startswith("4") and code.isdigit():
            codes.append(int(code))
    return codes


def normalize_endpoint(spec: Dict, path: str, method: str, operation: Dict,
                       path_item: Dict) -> Dict:
    """将某个端点统一为上层通用结构。method 需为小写。"""
    return {
        "method": method.upper(),
        "path": path,
        "summary": operation.get("summary"),
        "operationId": operation.get("operationId"),
        "description": operation.get("description"),
        "parameters": get_parameters(spec, path_item, operation),
        "request_body": get_request_body(spec, operation),
        "responses": operation.get("responses", {}) or {},
        "_spec": spec,
    }


def iter_endpoints(spec: Dict):
    """遍历所有端点，产出 normalize_endpoint 结果。"""
    paths = spec.get("paths", {}) or {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "delete", "patch"):
            operation = path_item.get(method)
            if isinstance(operation, dict):
                yield normalize_endpoint(spec, path, method, operation, path_item)