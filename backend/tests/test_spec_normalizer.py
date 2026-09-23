# -*- coding: utf-8 -*-
"""spec_normalizer 统一规范化层单测。"""
from app.services.spec_normalizer import (
    detect_version, resolve_ref, get_parameters, get_request_body,
    get_response_example, get_error_codes, iter_endpoints,
)


class TestDetectVersion:
    def test_openapi3(self, openapi3):
        assert detect_version(openapi3) == "openapi3"

    def test_swagger2(self, swagger2):
        assert detect_version(swagger2) == "swagger2"


class TestResolveRef:
    def test_swagger2(self, swagger2):
        assert resolve_ref(swagger2, "#/definitions/Pet").get("type") == "object"

    def test_openapi3(self, openapi3):
        assert resolve_ref(openapi3, "#/components/schemas/Pet").get("type") == "object"


class TestGetParameters:
    def test_excludes_body(self, swagger2):
        op = swagger2["paths"]["/pet"]["post"]
        assert get_parameters(swagger2, {}, op) == []

    def test_merges_path_and_op(self, swagger2):
        op = swagger2["paths"]["/pet/{petId}"]["get"]
        params = get_parameters(swagger2, swagger2["paths"]["/pet/{petId}"], op)
        names = {p["name"] for p in params}
        assert names == {"petId", "status"}


class TestGetRequestBody:
    def test_swagger2_required(self, swagger2):
        op = swagger2["paths"]["/pet"]["post"]
        rb = get_request_body(swagger2, op)
        assert rb["required"] == ["name", "photoUrls"]
        assert rb["content_type"] == "application/json"

    def test_openapi3_required(self, openapi3):
        op = openapi3["paths"]["/pets"]["post"]
        rb = get_request_body(openapi3, op)
        assert rb["required"] == ["name"]

    def test_missing_body(self, swagger2):
        op = swagger2["paths"]["/pet/{petId}"]["get"]
        rb = get_request_body(swagger2, op)
        assert rb["required"] == []


class TestGetResponseExample:
    def test_swagger2_keys(self, swagger2):
        op = swagger2["paths"]["/pet"]["post"]
        example = get_response_example(swagger2, op["responses"])
        assert set(example) == {"id", "name", "photoUrls"}

    def test_openapi3_keys(self, openapi3):
        op = openapi3["paths"]["/pets"]["post"]
        example = get_response_example(openapi3, op["responses"])
        assert set(example) == {"id", "name"}


class TestGetErrorCodes:
    def test_swagger2(self, swagger2):
        op = swagger2["paths"]["/pet"]["post"]
        assert get_error_codes(swagger2, op["responses"]) == [405]

    def test_openapi3(self, openapi3):
        op = openapi3["paths"]["/pets"]["post"]
        assert get_error_codes(openapi3, op["responses"]) == [400]


class TestIterEndpoints:
    def test_count(self, swagger2):
        assert len(list(iter_endpoints(swagger2))) == 2

    def test_method_upper(self, swagger2):
        ep = next(iter_endpoints(swagger2))
        assert ep["method"] == "POST"

    def test_endpoint_has_unified_body(self, swagger2):
        ep = next(iter_endpoints(swagger2))
        assert "content_type" in ep["request_body"]