"""Tests for core.model_router."""

import pytest

from core.model_router import AgentResponse, ModelRouter, ToolCall


def test_agent_response_no_tool_calls():
    """AgentResponse with no tool calls."""
    resp = AgentResponse(text="Hello!")
    assert resp.text == "Hello!"
    assert resp.has_tool_calls is False


def test_agent_response_with_tool_calls():
    """AgentResponse with tool calls."""
    resp = AgentResponse(
        text="",
        tool_calls=[ToolCall(name="search", arguments={"query": "test"})],
    )
    assert resp.has_tool_calls is True
    assert resp.tool_calls[0].name == "search"


def test_tool_call_has_id():
    """ToolCall should auto-generate an ID."""
    tc = ToolCall(name="test", arguments={})
    assert tc.id.startswith("call_")
