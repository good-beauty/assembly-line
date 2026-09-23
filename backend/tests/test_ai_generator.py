# -*- coding: utf-8 -*-
"""ai_generator 单测：并发批处理 + get_examples_from_spec 接入规范化层。"""
import types

import pytest

from app.services import ai_generator
from app.services.ai_generator import (
    get_examples_from_spec, generate_cases_for_endpoints_batch,
)


class TestGenerateCasesForEndpointsBatch:
    def _mk(self, i, path):
        return types.SimpleNamespace(
            id=i, method="GET", path=path, summary="s",
            parameters=[], request_body={}, responses={}, name=path,
        )

    def test_parallel_returns_all(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            ai_generator, "generate_cases_for_dataset",
            lambda method, path, *a, **k: calls.append(path) or [
                {"name": "c", "method": method, "url": path, "expected_status": 200},
            ],
        )
        endpoints = [self._mk(i, p) for i, p in enumerate(["/a", "/b", "/c", "/d"], 1)]
        res = ai_generator.generate_cases_for_endpoints_batch(endpoints, max_workers=4)
        assert set(res) == {1, 2, 3, 4}
        assert all(len(v) == 1 for v in res.values())

    def test_tolerates_single_failure(self, monkeypatch):
        def fake(method, path, *a, **k):
            if path == "/b":
                raise RuntimeError("boom")
            return [{"name": "c", "method": method, "url": path, "expected_status": 200}]
        monkeypatch.setattr(ai_generator, "generate_cases_for_dataset", fake)
        endpoints = [self._mk(i, p) for i, p in enumerate(["/a", "/b", "/c"], 1)]
        res = ai_generator.generate_cases_for_endpoints_batch(endpoints, max_workers=3)
        assert res[2] == []           # 失败接口降级为空
        assert len(res[1]) == 1
        assert set(res) == {1, 2, 3}


class TestGetExamplesFromSpec:
    def test_swagger2_required_fields(self, monkeypatch, swagger2):
        monkeypatch.setattr(ai_generator, "load_spec", lambda: swagger2)
        cons = get_examples_from_spec("POST", "/pet")
        # body 必填字段（Swagger 2.0 的 in:body）被正确提取
        assert "name" in cons["required_fields"]
        assert "photoUrls" in cons["required_fields"]

    def test_openapi3_required_fields(self, monkeypatch, openapi3):
        monkeypatch.setattr(ai_generator, "load_spec", lambda: openapi3)
        cons = get_examples_from_spec("POST", "/pets")
        assert "name" in cons["required_fields"]

    def test_path_and_query_params(self, monkeypatch, swagger2):
        monkeypatch.setattr(ai_generator, "load_spec", lambda: swagger2)
        cons = get_examples_from_spec("GET", "/pet/{petId}")
        assert "petId" in cons["path_params"]
        assert "status" in cons["query_params"]

    def test_error_responses(self, monkeypatch, swagger2):
        monkeypatch.setattr(ai_generator, "load_spec", lambda: swagger2)
        cons = get_examples_from_spec("POST", "/pet")
        codes = [e["status"] for e in cons["error_responses"]]
        assert 405 in codes