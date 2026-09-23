# -*- coding: utf-8 -*-
"""schemas.py Pydantic 校验单测。"""
import pytest
from pydantic import ValidationError

from app.schemas import RunTestsRequest, EndpointCreate, CaseGenerateRequest


class TestRunTestsRequest:
    def test_valid_ids(self):
        r = RunTestsRequest(test_case_ids=[1, 2, 3])
        assert r.test_case_ids == [1, 2, 3]

    def test_empty_ok(self):
        assert RunTestsRequest().test_case_ids is None

    def test_non_int_rejected(self):
        with pytest.raises(ValidationError):
            RunTestsRequest(test_case_ids=["a"])


class TestEndpointCreate:
    def test_valid(self):
        e = EndpointCreate(name="x", method="GET", path="/a")
        assert e.path == "/a"

    def test_lowercase_method_rejected(self):
        with pytest.raises(ValidationError):
            EndpointCreate(name="x", method="get", path="/a")

    def test_invalid_method_rejected(self):
        with pytest.raises(ValidationError):
            EndpointCreate(name="x", method="PATCHX", path="/a")

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            EndpointCreate(name="", method="GET", path="/a")


class TestCaseGenerateRequest:
    def test_valid(self):
        assert CaseGenerateRequest(endpoint_id=1).endpoint_id == 1

    def test_zero_rejected(self):
        with pytest.raises(ValidationError):
            CaseGenerateRequest(endpoint_id=0)