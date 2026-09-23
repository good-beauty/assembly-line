# -*- coding: utf-8 -*-
"""Pydantic 请求/响应模型，用于路由层入参校验与响应建模。"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class RunTestsRequest(BaseModel):
    """执行测试请求体：可选指定用例 ID 列表。"""
    test_case_ids: Optional[List[int]] = Field(
        default=None,
        description="要执行的测试用例 ID 列表，为空则执行全部"
    )


class EndpointCreate(BaseModel):
    """接口元数据（对应 api_endpoints 表）。"""
    name: str = Field(..., min_length=1, max_length=255)
    method: str = Field(..., pattern="^(GET|POST|PUT|DELETE|PATCH)$")
    path: str = Field(..., min_length=1)
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    request_body: Dict[str, Any] = Field(default_factory=dict)
    responses: Dict[str, Any] = Field(default_factory=dict)


class CaseGenerateRequest(BaseModel):
    """按接口生成用例请求体。"""
    endpoint_id: int = Field(..., gt=0)
    model: Optional[str] = Field(default=None, description="可选，覆盖默认模型")


class TestRunResponse(BaseModel):
    """执行结果响应。"""
    message: str
    total: int
    passed: int
    failed: int
    error: int = 0
    skipped: int = 0