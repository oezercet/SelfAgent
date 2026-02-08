"""Multi-provider model router using httpx.

Supports OpenAI, Anthropic (Claude), and Google (Gemini) with a unified
interface. All API calls use httpx — no vendor SDKs.

Provider-specific logic lives in core.providers and core.providers_extra.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from core.config import get_config
from core.providers import (
    AuthenticationError,
    ModelError,
    RateLimitError,
    chat_ollama,
    chat_openai,
)
from core.providers_extra import chat_anthropic, chat_google


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
            return await chat_openai(
                self._client, messages, tools, system_prompt, config
            )
        elif provider == "anthropic":
            return await chat_anthropic(
                self._client, messages, tools, system_prompt, config
            )
        elif provider == "google":
            return await chat_google(
                self._client, messages, tools, system_prompt, config
            )
        elif provider == "ollama":
            return await chat_ollama(
                self._client, messages, tools, system_prompt, config
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")


# Re-export error classes so existing catch blocks still work
__all__ = [
    "AgentResponse",
    "AuthenticationError",
    "ModelError",
    "ModelRouter",
    "RateLimitError",
    "ToolCall",
]
