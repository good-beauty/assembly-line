import json
import yaml
import requests
from typing import Dict, List

def load_swagger_content(content: bytes, filename: str) -> Dict:
    """根据文件后缀解析 JSON 或 YAML"""
    if filename.endswith(('.yaml', '.yml')):
        return yaml.safe_load(content)
    else:
        return json.loads(content)

def load_swagger_from_url(url: str) -> Dict:
    """从 URL 获取并解析 Swagger 文档"""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    if url.endswith(('.yaml', '.yml')):
        return yaml.safe_load(resp.text)
    else:
        return resp.json()

def extract_endpoints(swagger_data: Dict) -> List[Dict]:
    """提取接口元数据"""
    endpoints = []
    paths = swagger_data.get("paths", {})
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                continue
            endpoints.append({
                "name": operation.get("summary") or operation.get("operationId") or f"{method.upper()} {path}",
                "method": method.upper(),
                "path": path,
                "summary": operation.get("summary"),
                "description": operation.get("description"),
                "parameters": operation.get("parameters", []),
                "request_body": operation.get("requestBody"),
                "responses": operation.get("responses", {})
            })
    return endpoints