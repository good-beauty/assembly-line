import json
import yaml
import requests
from typing import Dict, List
from .spec_normalizer import iter_endpoints

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
    """提取接口元数据（统一 Swagger2/OpenAPI3）"""
    endpoints = []
    for ep in iter_endpoints(swagger_data):
        endpoints.append({
            "name": ep.get("summary") or ep.get("operationId") or f"{ep['method']} {ep['path']}",
            "method": ep["method"],
            "path": ep["path"],
            "summary": ep.get("summary"),
            "description": ep.get("description"),
            # 保留原始参数供 LLM 参考；request_body/responses 存统一后的结构
            "parameters": ep["parameters"],
            "request_body": ep["request_body"],
            "responses": ep["responses"],
        })
    return endpoints