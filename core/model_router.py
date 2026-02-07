"""Multi-provider model router using httpx.

Supports OpenAI, Anthropic (Claude), and Google (Gemini) with a unified
interface. All API calls use httpx — no vendor SDKs.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from core.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """A normalized tool call from any provider."""

    name: str
    arguments: dict[str, Any]
    id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")


@dataclass
class AgentResponse:
    """Unified response from any AI provider."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


OPENROUTER_FREE_FALLBACKS = [
    "google/gemma-3-27b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "qwen/qwen3-coder:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
]


class ModelRouter:
    """Routes messages to the user's chosen AI model."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system_prompt: str = "",
    ) -> AgentResponse:
        """Send messages to the configured model and return a unified response."""
        config = get_config().model
        provider = config.provider.lower()

        if provider in ("openai", "openrouter"):
            return await self._chat_openai(messages, tools, system_prompt, config)
        elif provider == "anthropic":
            return await self._chat_anthropic(messages, tools, system_prompt, config)
        elif provider == "google":
            return await self._chat_google(messages, tools, system_prompt, config)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # ── OpenAI ──────────────────────────────────────────────────────────

    async def _chat_openai(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        system_prompt: str,
        config: Any,
    ) -> AgentResponse:
        """Call OpenAI-compatible /v1/chat/completions."""
        if config.base_url:
            base_url = config.base_url.rstrip("/")
        elif config.provider == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        else:
            base_url = "https://api.openai.com/v1"

        url = f"{base_url}/chat/completions"
        provider_name = config.provider.capitalize()

        # Build list of models to try: primary first, then fallbacks
        is_free_openrouter = config.provider == "openrouter" and ":free" in config.model_name
        models_to_try = [config.model_name]
        if is_free_openrouter:
            for m in OPENROUTER_FREE_FALLBACKS:
                if m not in models_to_try:
                    models_to_try.append(m)

        original_model = config.model_name
        last_error = None

        for model in models_to_try:
            config.model_name = model
            current_tools = tools

            resp = await self._do_openai_request(
                url, config, messages, current_tools, system_prompt, use_system_role=True
            )

            # Retry without system role if model doesn't support it
            if resp.status_code == 400 and system_prompt:
                logger.info("Retrying %s without system role", model)
                resp = await self._do_openai_request(
                    url, config, messages, current_tools, system_prompt, use_system_role=False
                )

            # Retry without tools if model doesn't support tool use
            if resp.status_code == 404 and "tool use" in resp.text.lower():
                logger.info("Model %s doesn't support tools, retrying without", model)
                current_tools = None
                resp = await self._do_openai_request(
                    url, config, messages, current_tools, system_prompt, use_system_role=True
                )
                if resp.status_code == 400 and system_prompt:
                    resp = await self._do_openai_request(
                        url, config, messages, current_tools, system_prompt, use_system_role=False
                    )

            # Success — break out
            if resp.status_code == 200:
                break

            # Retriable error — try next model
            last_error = resp.text[:300]
            logger.warning(
                "Model %s failed (%d): %s. Trying next...",
                model, resp.status_code, last_error[:100],
            )

            # Only fallback for free models, not paid
            if not is_free_openrouter:
                break

        config.model_name = original_model
        data = self._handle_response(resp, provider_name)

        # Validate response format
        choices = data.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            # Log the unexpected response for debugging
            logger.error("Unexpected API response (no choices): %s", json.dumps(data)[:500])
            # Check if there's an error in the body
            if "error" in data:
                err_msg = data["error"]
                if isinstance(err_msg, dict):
                    err_msg = err_msg.get("message", str(err_msg))
                raise ModelError(f"{provider_name}: {err_msg}")
            raise ModelError(f"{provider_name} returned an unexpected response format.")

        message = choices[0].get("message", {})

        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                try:
                    args = tc["function"]["arguments"]
                    if isinstance(args, str):
                        args = json.loads(args)
                    tool_calls.append(
                        ToolCall(
                            name=tc["function"]["name"],
                            arguments=args,
                            id=tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                        )
                    )
                except (KeyError, json.JSONDecodeError) as e:
                    logger.warning("Skipping malformed tool call: %s", e)

        usage = data.get("usage", {})
        return AgentResponse(
            text=message.get("content") or "",
            tool_calls=tool_calls,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", config.model_name),
        )

    async def _do_openai_request(
        self,
        url: str,
        config: Any,
        messages: list[dict],
        tools: list[dict] | None,
        system_prompt: str,
        use_system_role: bool,
    ) -> httpx.Response:
        """Build and send an OpenAI-compatible request."""
        all_messages = []
        if system_prompt and use_system_role:
            all_messages.append({"role": "system", "content": system_prompt})
        elif system_prompt and not use_system_role:
            # Prepend system prompt to first user message for models
            # that don't support the system role (e.g. Gemma)
            all_messages.extend(messages)
            if all_messages and all_messages[0]["role"] == "user":
                all_messages[0] = {
                    **all_messages[0],
                    "content": f"[Instructions: {system_prompt}]\n\n{all_messages[0]['content']}",
                }
            else:
                all_messages.insert(0, {"role": "user", "content": f"[Instructions: {system_prompt}]"})
        if use_system_role:
            all_messages.extend(messages)

        body: dict[str, Any] = {
            "model": config.model_name,
            "messages": all_messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }

        if tools:
            body["tools"] = [
                {"type": "function", "function": t} for t in tools
            ]

        headers = {
            "Authorization": f"Bearer {config.get_active_key()}",
            "Content-Type": "application/json",
        }

        # OpenRouter requires these headers for free models
        if config.provider == "openrouter":
            headers["HTTP-Referer"] = "http://localhost:8765"
            headers["X-Title"] = "SelfAgent"

        return await self._client.post(
            url,
            headers=headers,
            json=body,
        )

    # ── Anthropic ───────────────────────────────────────────────────────

    async def _chat_anthropic(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        system_prompt: str,
        config: Any,
    ) -> AgentResponse:
        """Call Anthropic /v1/messages."""
        # Anthropic expects system as a top-level param, not in messages
        anthropic_messages = self._convert_messages_for_anthropic(messages)

        body: dict[str, Any] = {
            "model": config.model_name,
            "messages": anthropic_messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }
        if system_prompt:
            body["system"] = system_prompt

        if tools:
            body["tools"] = [self._tool_to_anthropic(t) for t in tools]

        resp = await self._client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": config.get_active_key(),
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=body,
        )

        data = self._handle_response(resp, "Anthropic")

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

    def _convert_messages_for_anthropic(
        self, messages: list[dict]
    ) -> list[dict]:
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

    def _tool_to_anthropic(self, tool: dict) -> dict:
        """Convert unified tool schema to Anthropic format."""
        return {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
        }

    # ── Google Gemini ───────────────────────────────────────────────────

    async def _chat_google(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        system_prompt: str,
        config: Any,
    ) -> AgentResponse:
        """Call Google Gemini generateContent endpoint."""
        contents = self._convert_messages_for_gemini(messages, system_prompt)

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
                        self._tool_to_gemini(t) for t in tools
                    ]
                }
            ]

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config.model_name}:generateContent?key={config.get_active_key()}"
        )

        resp = await self._client.post(
            url,
            headers={"Content-Type": "application/json"},
            json=body,
        )

        data = self._handle_response(resp, "Google")

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

    def _convert_messages_for_gemini(
        self, messages: list[dict], system_prompt: str
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

    def _tool_to_gemini(self, tool: dict) -> dict:
        """Convert unified tool schema to Gemini functionDeclaration."""
        decl: dict[str, Any] = {
            "name": tool["name"],
            "description": tool.get("description", ""),
        }
        params = tool.get("parameters")
        if params:
            decl["parameters"] = params
        return decl

    # ── Helpers ──────────────────────────────────────────────────────────

    def _handle_response(self, resp: httpx.Response, provider: str) -> dict:
        """Parse response, raise on errors."""
        if resp.status_code == 401:
            raise AuthenticationError(
                f"{provider} API key is invalid. Check your config.yaml."
            )
        if resp.status_code == 429:
            raise RateLimitError(
                f"{provider} rate limit reached. Please wait and try again."
            )
        if resp.status_code >= 400:
            detail = resp.text[:500]
            # Friendlier message for common OpenRouter errors
            if resp.status_code == 404 and "data policy" in detail.lower():
                raise ModelError(
                    f"{provider}: Free model blocked by your data policy settings. "
                    f"Go to https://openrouter.ai/settings/privacy and enable "
                    f"'Allow models that may train on inputs'."
                )
            raise ModelError(
                f"{provider} API error ({resp.status_code}): {detail}"
            )

        data = resp.json()
        try:
            usage = data.get("usage") or data.get("usageMetadata") or {}
            usage_tokens = sum(v for v in usage.values() if isinstance(v, (int, float)))
            if usage_tokens:
                logger.info("%s token usage: %d total", provider, usage_tokens)
        except Exception:
            pass  # Don't fail on usage tracking

        return data


class ModelError(Exception):
    """Base error for model API issues."""


class AuthenticationError(ModelError):
    """Invalid API key."""


class RateLimitError(ModelError):
    """Rate limit exceeded."""
