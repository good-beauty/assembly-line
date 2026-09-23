# -*- coding: utf-8 -*-
"""swagger_parser 单测：extract_endpoints 调用了规范化层。"""
from app.services.swagger_parser import extract_endpoints


class TestExtractEndpoints:
    def test_count(self, swagger2):
        assert len(extract_endpoints(swagger2)) == 2

    def test_name_uses_summary(self, swagger2):
        out = extract_endpoints(swagger2)
        assert out[0]["name"] == "Add a new pet"

    def test_uses_fallback_name(self, swagger2):
        # 临时去掉 summary，验证回退到 operationId / method+path
        data = {
            "swagger": "2.0",
            "paths": {"/ping": {"get": {"responses": {"200": {"description": "ok"}}}}},
        }
        out = extract_endpoints(data)
        assert out[0]["name"] == "GET /ping"

    def test_request_body_unified(self, swagger2):
        out = extract_endpoints(swagger2)
        assert "content_type" in out[0]["request_body"]

    def test_method_upper(self, swagger2):
        out = extract_endpoints(swagger2)
        assert out[0]["method"] == "POST"