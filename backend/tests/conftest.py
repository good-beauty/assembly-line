# -*- coding: utf-8 -*-
"""pytest 全局夹具与依赖注入，避免触发真实 LLM / 数据库连接。"""
import os
import sys
import types

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(TESTS_DIR)  # backend/
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# 避免 ai_generator 模块加载时因缺 LLM_API_KEY 抛 RuntimeError
os.environ.setdefault("LLM_API_KEY", "test-key")
# 避免 database 连接真实 MySQL（用内存 sqlite 即可）
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["IN_DOCKER"] = "false"


def _install_dashscope_mock():
    """依赖树里有 dashscope，但本机沙箱未必安装。用伪模块顶替。"""
    if "dashscope" in sys.modules:
        return sys.modules["dashscope"]
    ds = types.ModuleType("dashscope")
    gen = types.ModuleType("dashscope.Generation")
    gen.call = lambda **kw: None
    ds.Generation = gen
    ds.api_key = None
    sys.modules["dashscope"] = ds
    sys.modules["dashscope.Generation"] = gen
    return ds


_install_dashscope_mock()


# ===== 共享测试样本 =====
import pytest

SWAGGER2 = {
    "swagger": "2.0",
    "paths": {
        "/pet": {
            "post": {
                "summary": "Add a new pet",
                "parameters": [{
                    "name": "body", "in": "body", "required": True,
                    "schema": {"$ref": "#/definitions/Pet"},
                }],
                "responses": {
                    "200": {"description": "ok", "schema": {"$ref": "#/definitions/Pet"}},
                    "405": {"description": "Invalid input"},
                },
            }
        },
        "/pet/{petId}": {
            "get": {
                "parameters": [
                    {"name": "petId", "in": "path", "required": True, "type": "integer"},
                    {"name": "status", "in": "query", "type": "string", "required": False},
                ],
                "responses": {
                    "200": {"description": "ok", "schema": {"$ref": "#/definitions/Pet"}},
                    "404": {"description": "not found"},
                },
            }
        },
    },
    "definitions": {
        "Pet": {
            "type": "object",
            "required": ["name", "photoUrls"],
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "photoUrls": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}

OPENAPI3 = {
    "openapi": "3.0.0",
    "paths": {
        "/pets": {
            "post": {
                "summary": "Create pet",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}},
                },
                "responses": {
                    "200": {"description": "ok", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}}},
                    "400": {"description": "bad"},
                },
            }
        }
    },
    "components": {
        "schemas": {
            "Pet": {
                "type": "object",
                "required": ["name"],
                "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
            },
        },
    },
}

JUNIT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testcase name="test_1_ok"/>
  <testcase name="test_2_bad"><failure message="AssertionError: 404"/></testcase>
  <testcase name="test_3_err"><error message="ConnectionError"/></testcase>
  <testcase name="not_a_case"/>
</testsuites>
"""


@pytest.fixture
def swagger2():
    return SWAGGER2


@pytest.fixture
def openapi3():
    return OPENAPI3


@pytest.fixture
def junit_xml(tmp_path):
    p = tmp_path / "results.xml"
    p.write_text(JUNIT_XML, encoding="utf-8")
    return str(p)