"""Tests for parse_json_response covering every malformed-output pattern we've seen."""

import pytest

from moderation.utils import parse_json_response


def test_standard_json():
    assert parse_json_response('{"key": "value"}') == {"key": "value"}


def test_markdown_fenced_json():
    raw = '```json\n{"key": "value"}\n```'
    assert parse_json_response(raw) == {"key": "value"}


def test_markdown_fenced_no_lang():
    raw = '```\n{"key": "value"}\n```'
    assert parse_json_response(raw) == {"key": "value"}


def test_literal_newline_in_string():
    # Model puts a real newline inside a string — the bug we saw at char 282
    raw = (
        '{\n  "decision": "flagged",\n  "reasoning": "Line one\nLine two",\n  "confidence": 0.9\n}'
    )
    result = parse_json_response(raw)
    assert result["decision"] == "flagged"
    assert "Line one" in result["reasoning"]


def test_literal_tab_in_string():
    raw = '{"reasoning": "col1\tcol2", "decision": "allowed"}'
    result = parse_json_response(raw)
    assert "col1" in result["reasoning"]


def test_single_quoted_dict():
    # Model generates Python-style dict
    raw = "{'decision': 'flagged', 'confidence': 0.9}"
    result = parse_json_response(raw)
    assert result["decision"] == "flagged"


def test_trailing_comma():
    raw = '{"decision": "allowed", "confidence": 0.8,}'
    assert parse_json_response(raw)["decision"] == "allowed"


def test_json_embedded_in_prose():
    raw = 'Sure, here is the result:\n{"key": "value"}\nThat is all.'
    assert parse_json_response(raw) == {"key": "value"}


def test_nested_braces_in_string_value():
    # Braces inside a string value shouldn't confuse extraction
    raw = '{"reasoning": "The post uses {suspicious} formatting.", "decision": "flagged"}'
    result = parse_json_response(raw)
    assert result["decision"] == "flagged"


def test_none_content_raises():
    with pytest.raises(ValueError, match="no content"):
        parse_json_response(None)


def test_completely_invalid_raises():
    with pytest.raises(ValueError):
        parse_json_response("this is not json at all <<<")


def test_null_values_preserved():
    raw = '{"severity": null, "scam_category": null, "decision": "allowed"}'
    result = parse_json_response(raw)
    assert result["severity"] is None
    assert result["scam_category"] is None
