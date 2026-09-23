# -*- coding: utf-8 -*-
"""test_executor 单测：安全渲染、JUnit 解析、函数名清洗。"""
from app.services.test_executor import (
    sanitize_name, to_python_literal, render_assertions, parse_junit_results,
)


class TestSanitizeName:
    def test_ascii_passthrough(self):
        assert sanitize_name("hello world") == "hello_world"

    def test_chinese_kept(self):
        # \W 是 unicode 感知,中文属 \w,保留
        assert sanitize_name("添加宠物") == "添加宠物"

    def test_mixed_chinese_and_space(self):
        assert sanitize_name("添加 宠物") == "添加_宠物"

    def test_leading_digit(self):
        assert sanitize_name("7 ok") == "_7_ok"


class TestToPythonLiteral:
    def test_scalars(self):
        assert to_python_literal(None) == "None"
        assert to_python_literal(True) == "True"
        assert to_python_literal(False) == "False"
        assert to_python_literal(3) == "3"

    def test_dict(self):
        assert to_python_literal({"a": True}) == "{'a': True}"

    def test_nested(self):
        out = to_python_literal({"a": [None, 1]})
        assert out == "{'a': [None, 1]}"


class TestRenderAssertions:
    def test_contains(self):
        assert render_assertions([{"contains": "Dog"}]) == ["assert 'Dog' in response.text"]

    def test_field_exists(self):
        out = render_assertions([{"field_exists": "id"}])
        assert out == ["assert 'id' in response.json(), 'missing field 'id''"]

    def test_field_equals(self):
        out = render_assertions([{"field_equals": ["name", "Dog"]}])
        assert out == ["assert response.json().get('name') == 'Dog'"]

    def test_ignores_unknown(self):
        assert render_assertions([{"foo": 1}, "str", None]) == []

    def test_injection_is_literal(self):
        # 恶意 contains 串被 repr 转义为字符串字面量，不含可执行代码的换行拼接
        out = render_assertions([{"contains": '${os.system("rm")}'}])
        assert len(out) == 1
        assert "in response.text" in out[0]


class TestParseJunitResults:
    def test_passed(self, junit_xml):
        parsed = parse_junit_results(junit_xml)
        assert parsed.get(1) == ("passed", None)

    def test_failure_message(self, junit_xml):
        parsed = parse_junit_results(junit_xml)
        assert parsed.get(2)[0] == "failed"
        assert "AssertionError" in parsed.get(2)[1]

    def test_error(self, junit_xml):
        parsed = parse_junit_results(junit_xml)
        assert parsed.get(3)[0] == "error"

    def test_ignores_non_case(self, junit_xml):
        parsed = parse_junit_results(junit_xml)
        assert 999 not in parsed