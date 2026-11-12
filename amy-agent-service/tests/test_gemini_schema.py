"""Gemini tool-parameter schema sanitization (no additionalProperties in payload)."""

from __future__ import annotations

from typing import Any

from app.providers.gemini import _tools_payload, sanitize_gemini_schema
from app.providers.tool_types import ToolSpec
from app.services.admin_chat_tools import ADMIN_TOOL_SPECS


def _assert_no_key(node: Any, forbidden: str) -> None:
    if isinstance(node, list):
        for item in node:
            _assert_no_key(item, forbidden)
        return
    if isinstance(node, dict):
        assert forbidden not in node
        for value in node.values():
            _assert_no_key(value, forbidden)


def test_sanitize_strips_additional_properties_nested() -> None:
    schema = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["hot", "warm"],
                "additionalProperties": False,
            },
            "nested": {
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "examples": [{"status": "hot"}],
        "required": ["status"],
    }
    cleaned = sanitize_gemini_schema(schema)
    _assert_no_key(cleaned, "additionalProperties")
    _assert_no_key(cleaned, "$schema")
    _assert_no_key(cleaned, "examples")
    assert cleaned["type"] == "object"
    assert cleaned["required"] == ["status"]
    assert cleaned["properties"]["status"]["enum"] == ["hot", "warm"]
    assert cleaned["properties"]["nested"]["properties"]["x"]["type"] == "integer"


def test_tools_payload_strips_admin_tool_additional_properties() -> None:
    """Regression: analytics tools ship additionalProperties:false internally."""
    # Preconditions — internal specs still have the JSON Schema keyword.
    assert any(
        isinstance(spec.parameters, dict) and "additionalProperties" in spec.parameters
        for spec in ADMIN_TOOL_SPECS
    )

    payload = _tools_payload(ADMIN_TOOL_SPECS)
    assert payload is not None
    decls = payload["functionDeclarations"]
    assert len(decls) == len(ADMIN_TOOL_SPECS)
    for decl in decls:
        _assert_no_key(decl.get("parameters"), "additionalProperties")
        _assert_no_key(decl.get("parameters"), "$schema")
        _assert_no_key(decl.get("parameters"), "examples")


def test_tools_payload_preserves_supported_fields() -> None:
    tools = [
        ToolSpec(
            name="demo",
            description="demo tool",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 25,
                        "description": "Max rows",
                    }
                },
                "required": ["limit"],
                "additionalProperties": False,
            },
        )
    ]
    payload = _tools_payload(tools)
    assert payload is not None
    params = payload["functionDeclarations"][0]["parameters"]
    assert "additionalProperties" not in params
    assert params["properties"]["limit"]["minimum"] == 1
    assert params["properties"]["limit"]["maximum"] == 25
    assert params["required"] == ["limit"]
