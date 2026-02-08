"""Provider-specific logic for Anthropic (Claude) and Google (Gemini).

All provider functions accept an httpx.AsyncClient and config, returning
AgentResponse.  This module is used internally by ModelRouter — import
from core.model_router instead.
"""

import logging
from typing import Any

import httpx

from core.providers import handle_response

logger = logging.getLogger(__name__)


# ── Anthropic ──────────────────────────────────────────────────────────

def _convert_messages_for_anthropic(messages: list[dict]) -> list[dict]:
    """Convert messages to Anthropic format, handling tool results."""
    result = []
    for msg in messages:
        role = msg["role"]
        if role == "system":
            # Skip — system is handled as a top-level param
            continue
        elif role == "tool":
            # Anthropic expects tool results as user messages
            result.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id", ""),
                            "content": msg.get("content", ""),
                        }
                    ],
                }
            )
        elif role == "assistant" and msg.get("tool_calls"):
            # Convert OpenAI-style tool_calls to Anthropic content blocks
            content = []
            if msg.get("content"):
                content.append({"type": "text", "text": msg["content"]})
            for tc in msg["tool_calls"]:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["arguments"],
                    }
                )
            result.append({"role": "assistant", "content": content})
        else:
            result.append({"role": role, "content": msg.get("content", "")})
    return result


def _tool_to_anthropic(tool: dict) -> dict:
    """Convert unified tool schema to Anthropic format."""
    return {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
    }


async def chat_anthropic(
    client: httpx.AsyncClient,
    messages: list[dict],
    tools: list[dict] | None,
    system_prompt: str,
    config: Any,
) -> "AgentResponse":
    """Call Anthropic /v1/messages."""
    from core.model_router import AgentResponse, ToolCall

    anthropic_messages = _convert_messages_for_anthropic(messages)

    body: dict[str, Any] = {
        "model": config.model_name,
        "messages": anthropic_messages,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }
    if system_prompt:
        body["system"] = system_prompt

    if tools:
        body["tools"] = [_tool_to_anthropic(t) for t in tools]

    resp = await client.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": config.get_active_key(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json=body,
    )

    data = handle_response(resp, "Anthropic")

    text_parts = []
    tool_calls = []
    for block in data.get("content", []):
        if block["type"] == "text":
            text_parts.append(block["text"])
        elif block["type"] == "tool_use":
            tool_calls.append(
                ToolCall(
                    name=block["name"],
                    arguments=block.get("input", {}),
                    id=block["id"],
                )
            )

    usage = data.get("usage", {})
    return AgentResponse(
        text="\n".join(text_parts),
        tool_calls=tool_calls,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        model=data.get("model", config.model_name),
    )


# ── Google Gemini ──────────────────────────────────────────────────────

def _convert_messages_for_gemini(
    messages: list[dict], system_prompt: str
) -> list[dict]:
    """Convert messages to Gemini contents format.

    Gemini requires that ALL functionResponse parts for a single
    multi-tool-call turn are grouped in one content block.
    Screenshots from tool results are sent as a user message with
    inlineData after all function responses in the block.
    """
    contents = []
    pending_screenshots: list[str] = []

    for i, msg in enumerate(messages):
        role = msg["role"]
        if role == "system":
            continue
        elif role == "tool":
            # Merge consecutive tool results into one function block
            part = {
                "functionResponse": {
                    "name": msg.get("name", "tool"),
                    "response": {"result": msg.get("content", "")},
                }
            }
            if contents and contents[-1].get("role") == "function":
                # Append to existing function block
                contents[-1]["parts"].append(part)
            else:
                contents.append({"role": "function", "parts": [part]})

            # Collect screenshot if present
            if msg.get("screenshot_b64"):
                pending_screenshots.append(msg["screenshot_b64"])

            # After the last consecutive tool message, inject screenshot
            next_is_tool = (
                i + 1 < len(messages)
                and messages[i + 1].get("role") == "tool"
            )
            if not next_is_tool and pending_screenshots:
                contents.append({
                    "role": "user",
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": pending_screenshots[-1],
                            }
                        },
                        {"text": "Screenshot of the current browser page."},
                    ],
                })
                pending_screenshots.clear()
        elif role == "assistant":
            parts = []
            if msg.get("content"):
                parts.append({"text": msg["content"]})
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    parts.append(
                        {
                            "functionCall": {
                                "name": tc["name"],
                                "args": tc["arguments"],
                            }
                        }
                    )
            contents.append({"role": "model", "parts": parts})
        else:
            gemini_role = "user" if role == "user" else "model"
            contents.append(
                {
                    "role": gemini_role,
                    "parts": [{"text": msg.get("content", "")}],
                }
            )
    return contents


def _tool_to_gemini(tool: dict) -> dict:
    """Convert unified tool schema to Gemini functionDeclaration."""
    decl: dict[str, Any] = {
        "name": tool["name"],
        "description": tool.get("description", ""),
    }
    params = tool.get("parameters")
    if params:
        decl["parameters"] = params
    return decl


async def chat_google(
    client: httpx.AsyncClient,
    messages: list[dict],
    tools: list[dict] | None,
    system_prompt: str,
    config: Any,
) -> "AgentResponse":
    """Call Google Gemini generateContent endpoint."""
    from core.model_router import AgentResponse, ToolCall

    contents = _convert_messages_for_gemini(messages, system_prompt)

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": config.max_tokens,
            "temperature": config.temperature,
        },
    }

    if system_prompt:
        body["systemInstruction"] = {
            "parts": [{"text": system_prompt}]
        }

    if tools:
        body["tools"] = [
            {
                "functionDeclarations": [
                    _tool_to_gemini(t) for t in tools
                ]
            }
        ]

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.model_name}:generateContent?key={config.get_active_key()}"
    )

    resp = await client.post(
        url,
        headers={"Content-Type": "application/json"},
        json=body,
    )

    data = handle_response(resp, "Google")

    candidate = data.get("candidates", [{}])[0]
    content = candidate.get("content", {})
    parts = content.get("parts", [])

    text_parts = []
    tool_calls = []
    for part in parts:
        if "text" in part:
            text_parts.append(part["text"])
        elif "functionCall" in part:
            fc = part["functionCall"]
            tool_calls.append(
                ToolCall(
                    name=fc["name"],
                    arguments=fc.get("args", {}),
                )
            )

    usage = data.get("usageMetadata", {})
    return AgentResponse(
        text="\n".join(text_parts),
        tool_calls=tool_calls,
        input_tokens=usage.get("promptTokenCount", 0),
        output_tokens=usage.get("candidatesTokenCount", 0),
        model=config.model_name,
    )
