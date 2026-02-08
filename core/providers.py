"""Provider-specific logic: shared utilities and OpenAI/OpenRouter.

All provider functions accept an httpx.AsyncClient and config, returning
AgentResponse.  This module is used internally by ModelRouter — import
from core.model_router instead.
"""

import json
import logging
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ── Error classes ──────────────────────────────────────────────────────

class ModelError(Exception):
    """Base error for model API issues."""


class AuthenticationError(ModelError):
    """Invalid API key."""


class RateLimitError(ModelError):
    """Rate limit exceeded."""


# ── Constants ──────────────────────────────────────────────────────────

OPENROUTER_FREE_FALLBACKS = [
    "google/gemma-3-27b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "qwen/qwen3-coder:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
]


# ── Response helpers ───────────────────────────────────────────────────

def handle_response(resp: httpx.Response, provider: str) -> dict:
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


# ── OpenAI / OpenRouter ───────────────────────────────────────────────

async def _do_openai_request(
    client: httpx.AsyncClient,
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

    return await client.post(
        url,
        headers=headers,
        json=body,
    )


async def chat_openai(
    client: httpx.AsyncClient,
    messages: list[dict],
    tools: list[dict] | None,
    system_prompt: str,
    config: Any,
) -> "AgentResponse":
    """Call OpenAI-compatible /v1/chat/completions."""
    from core.model_router import AgentResponse, ToolCall

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

        resp = await _do_openai_request(
            client, url, config, messages, current_tools, system_prompt, use_system_role=True
        )

        # Retry without system role if model doesn't support it
        if resp.status_code == 400 and system_prompt:
            logger.info("Retrying %s without system role", model)
            resp = await _do_openai_request(
                client, url, config, messages, current_tools, system_prompt, use_system_role=False
            )

        # Retry without tools if model doesn't support tool use
        if resp.status_code == 404 and "tool use" in resp.text.lower():
            logger.info("Model %s doesn't support tools, retrying without", model)
            current_tools = None
            resp = await _do_openai_request(
                client, url, config, messages, current_tools, system_prompt, use_system_role=True
            )
            if resp.status_code == 400 and system_prompt:
                resp = await _do_openai_request(
                    client, url, config, messages, current_tools, system_prompt, use_system_role=False
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
    data = handle_response(resp, provider_name)

    # Validate response format
    choices = data.get("choices")
    if not choices or not isinstance(choices, list) or len(choices) == 0:
        logger.error("Unexpected API response (no choices): %s", json.dumps(data)[:500])
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


# ── Ollama (Local) ────────────────────────────────────────────────────

async def chat_ollama(
    client: httpx.AsyncClient,
    messages: list[dict],
    tools: list[dict] | None,
    system_prompt: str,
    config: Any,
) -> "AgentResponse":
    """Call a local Ollama instance via its OpenAI-compatible endpoint."""
    from core.model_router import AgentResponse, ToolCall

    base_url = (config.ollama_base_url or "http://localhost:11434").rstrip("/")
    url = f"{base_url}/v1/chat/completions"

    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    body: dict[str, Any] = {
        "model": config.model_name,
        "messages": all_messages,
        "temperature": config.temperature,
    }
    if tools:
        body["tools"] = [{"type": "function", "function": t} for t in tools]

    try:
        resp = await client.post(
            url,
            headers={"Content-Type": "application/json"},
            json=body,
        )
    except httpx.ConnectError:
        raise ModelError(
            "Cannot connect to Ollama. Is it running? "
            "Start it with: ollama serve"
        )

    # Retry without tools if unsupported
    if resp.status_code >= 400 and tools and "tool" in resp.text.lower():
        logger.info("Ollama model %s doesn't support tools, retrying without", config.model_name)
        del body["tools"]
        try:
            resp = await client.post(url, headers={"Content-Type": "application/json"}, json=body)
        except httpx.ConnectError:
            raise ModelError("Cannot connect to Ollama. Is it running? Start it with: ollama serve")

    if resp.status_code == 404:
        raise ModelError(
            f"Ollama model '{config.model_name}' not found. "
            f"Pull it with: ollama pull {config.model_name}"
        )
    if resp.status_code >= 400:
        raise ModelError(f"Ollama error ({resp.status_code}): {resp.text[:300]}")

    data = resp.json()
    choices = data.get("choices")
    if not choices:
        raise ModelError("Ollama returned an unexpected response format.")

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
