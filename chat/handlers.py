"""Message handling functions for the WebSocket chat server."""

import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import WebSocket

from core.agent import Agent
from core.config import get_config, update_config_from_dict

logger = logging.getLogger(__name__)


async def send_ws(
    ws: WebSocket,
    msg_type: str,
    content: str,
    role: str = "system",
    metadata: dict | None = None,
) -> None:
    """Send a message to the frontend."""
    await ws.send_json(
        {
            "type": msg_type,
            "content": content,
            "role": role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
    )


async def handle_config(ws: WebSocket, data: dict) -> None:
    """Apply config updates from the frontend settings panel."""
    updates = data.get("config", {})
    if not updates:
        return

    try:
        model_updates = updates.get("model", {})

        # Reject old-format config (has generic api_key but no per-provider keys).
        # This prevents stale tabs from overriding the active config.
        is_ollama = model_updates.get("provider") == "ollama"
        has_provider_keys = is_ollama or any(
            model_updates.get(k)
            for k in ("openai_key", "anthropic_key", "google_key", "openrouter_key")
        )
        if not has_provider_keys and "api_key" in model_updates:
            logger.warning(
                "Ignoring old-format config from stale tab: provider=%s",
                model_updates.get("provider", "?"),
            )
            return

        logger.info(
            "Config update: provider=%s, model=%s",
            model_updates.get("provider", "?"),
            model_updates.get("model_name", "?"),
        )
        update_config_from_dict(updates)

        config = get_config()
        logger.info(
            "Active config now: provider=%s, model=%s, active_key=%s",
            config.model.provider,
            config.model.model_name,
            config.model.get_active_key()[:10] + "..." if config.model.get_active_key() else "EMPTY",
        )
        await send_ws(ws, "status", "Settings updated.")
    except Exception as e:
        logger.exception("Failed to update config")
        await send_ws(ws, "error", f"Failed to update settings: {e}")


async def handle_check_ollama(ws: WebSocket, data: dict) -> None:
    """Check Ollama status and return installed models."""
    config = get_config()
    base_url = (config.model.ollama_base_url or "http://localhost:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]
            await send_ws(ws, "ollama_status", "", metadata={
                "status": "running", "models": model_names, "url": base_url,
            })
        else:
            await send_ws(ws, "ollama_status", "", metadata={"status": "error"})
    except httpx.ConnectError:
        await send_ws(ws, "ollama_status", "", metadata={"status": "not_running"})
    except Exception:
        await send_ws(ws, "ollama_status", "", metadata={"status": "error"})


async def handle_pull_ollama(ws: WebSocket, data: dict) -> None:
    """Pull (download) an Ollama model with streaming progress."""
    model_name = data.get("model", "").strip()
    if not model_name:
        await send_ws(ws, "error", "Model name required.")
        return
    config = get_config()
    base_url = (config.model.ollama_base_url or "http://localhost:11434").rstrip("/")
    try:
        await send_ws(ws, "ollama_pull_progress", f"Pulling {model_name}...",
                       metadata={"model": model_name, "progress": 0})
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream("POST", f"{base_url}/api/pull",
                                      json={"name": model_name}) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    status = chunk.get("status", "")
                    total = chunk.get("total", 0)
                    completed = chunk.get("completed", 0)
                    pct = int(completed / total * 100) if total else 0
                    await send_ws(ws, "ollama_pull_progress", status,
                                   metadata={"model": model_name, "progress": pct})
        await send_ws(ws, "ollama_pull_done", f"Model '{model_name}' ready!",
                       metadata={"model": model_name})
    except httpx.ConnectError:
        await send_ws(ws, "error", "Ollama is not running.")
    except Exception as e:
        await send_ws(ws, "error", f"Pull failed: {e}")


async def handle_message(ws: WebSocket, data: dict, agent: Agent | None) -> None:
    """Process a user chat message through the agent."""
    content = data.get("content", "").strip()
    if not content:
        return

    if not agent:
        await send_ws(ws, "error", "Agent not initialized.")
        return

    config = get_config()
    active_key = config.model.get_active_key()
    if config.model.provider != "ollama" and (not active_key or active_key == "your-api-key-here"):
        await send_ws(
            ws,
            "error",
            "Please set your API key in the settings panel (click the gear icon).",
        )
        return

    # Send typing indicator
    await send_ws(ws, "typing", "")

    try:
        async for event in agent.process_message(content):
            etype = event["type"]
            if etype == "text":
                await send_ws(ws, "message", event["content"], role="assistant")
            elif etype == "tool_start":
                await send_ws(
                    ws,
                    "status",
                    f"Using tool: {event['name']}...",
                    metadata={"tool": event["name"], "arguments": event["arguments"]},
                )
            elif etype == "tool_result":
                await send_ws(
                    ws,
                    "tool_result",
                    event["result"],
                    metadata={"tool": event["name"]},
                )
            elif etype == "error":
                await send_ws(ws, "error", event["content"])
            elif etype == "usage":
                await send_ws(
                    ws,
                    "usage",
                    "",
                    metadata={
                        "input_tokens": event["input_tokens"],
                        "output_tokens": event["output_tokens"],
                        "total_input_tokens": event["total_input_tokens"],
                        "total_output_tokens": event["total_output_tokens"],
                        "model": event.get("model", ""),
                    },
                )
            elif etype == "done":
                await send_ws(ws, "done", "")
    except Exception as e:
        logger.exception("Error processing message")
        await send_ws(ws, "error", f"Something went wrong: {e}")
