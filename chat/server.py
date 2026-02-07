"""WebSocket chat server for SelfAgent."""

import asyncio
import json
import logging
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from core.agent import Agent
from core.config import get_config, update_config_from_dict
from core.memory import Memory
from core.model_router import ModelRouter
from core.task_manager import TaskManager
from tools.api_tester import ApiTesterTool
from tools.code_writer import CodeWriterTool
from tools.database_tool import DatabaseTool
from tools.file_manager import FileManagerTool
from tools.git_tool import GitTool
from tools.registry import ToolRegistry
from tools.terminal import TerminalTool
from tools.web_browser import WebBrowserTool
from tools.web_search import WebSearchTool
from tools.website_builder import WebsiteBuilderTool
from tools.clipboard import ClipboardTool
from tools.data_analyzer import DataAnalyzerTool
from tools.downloader import DownloaderTool
from tools.email_tool import EmailTool
from tools.image_tool import ImageTool
from tools.pdf_tool import PdfTool
from tools.scheduler import SchedulerTool
from tools.screenshot import ScreenshotTool
from tools.system_control import SystemControlTool
from tools.plugin_loader import load_plugins

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
UPLOAD_DIR = Path(__file__).parent.parent / "storage" / "uploads"

app = FastAPI(title="SelfAgent")

# Global instances (created on startup)
agent: Agent | None = None
memory: Memory | None = None
task_manager: TaskManager | None = None
# Lock to prevent concurrent message processing
_processing_lock = asyncio.Lock()
# Track active WebSocket connection (only one at a time)
_active_ws: WebSocket | None = None


@app.on_event("startup")
async def startup() -> None:
    """Initialize memory, task manager, and agent on server start."""
    global agent, memory, task_manager
    config = get_config()

    # Initialize persistent storage
    memory = Memory(
        max_short_term=config.memory.max_short_term,
        auto_summarize=config.memory.auto_summarize,
    )
    await memory.initialize()

    task_manager = TaskManager()
    await task_manager.initialize()

    router = ModelRouter()
    registry = ToolRegistry()

    # Register tools
    registry.register(WebSearchTool())
    registry.register(FileManagerTool())
    registry.register(WebBrowserTool())
    registry.register(TerminalTool())
    registry.register(CodeWriterTool())
    registry.register(GitTool())
    registry.register(DatabaseTool())
    registry.register(ApiTesterTool())
    registry.register(WebsiteBuilderTool())

    # Phase 5 — Productivity tools
    registry.register(ScreenshotTool())
    registry.register(SystemControlTool())
    registry.register(ClipboardTool())
    registry.register(ImageTool())
    registry.register(PdfTool())
    registry.register(DataAnalyzerTool())
    registry.register(DownloaderTool())
    registry.register(SchedulerTool())
    registry.register(EmailTool())

    # Load community plugins from plugins/ directory
    load_plugins(registry)

    agent = Agent(
        model_router=router,
        tool_registry=registry,
        memory=memory,
        task_manager=task_manager,
    )

    logger.info(
        "SelfAgent started — http://%s:%d",
        config.server.host,
        config.server.port,
    )

    if config.server.open_browser:
        url = f"http://{config.server.host}:{config.server.port}"
        webbrowser.open(url)


@app.on_event("shutdown")
async def shutdown() -> None:
    """Clean up resources."""
    try:
        if agent:
            await agent.router.close()
            browser_tool = agent.tools.get("web_browser")
            if browser_tool:
                await browser_tool.close_browser()
        if memory:
            await memory.close()
        if task_manager:
            await task_manager.close()
    except Exception:
        logger.exception("Error during shutdown")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Main WebSocket chat endpoint."""
    global _active_ws
    await ws.accept()
    logger.info("Client connected")

    # Only the most recent connection is the active one
    _active_ws = ws

    try:
        while True:
            raw = await ws.receive_text()

            # Ignore messages from stale connections
            if ws is not _active_ws:
                logger.info("Ignoring message from stale WebSocket connection")
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send(ws, "error", "Invalid message format.")
                continue
            msg_type = data.get("type", "message")

            if msg_type == "config":
                # Frontend sending config updates (API key, model, etc.)
                await _handle_config(ws, data)
            elif msg_type == "message":
                # Use lock to prevent concurrent processing
                if _processing_lock.locked():
                    await _send(ws, "error", "Already processing a message. Please wait.")
                    continue
                async with _processing_lock:
                    await _handle_message(ws, data)
            elif msg_type == "get_tools":
                if agent:
                    tools_list = agent.tools.list_tools_with_status()
                    await _send(ws, "tools_list", "", metadata={"tools": tools_list})
            elif msg_type == "toggle_tool":
                if agent:
                    name = data.get("tool_name", "")
                    enabled = data.get("enabled", True)
                    ok = agent.tools.set_tool_enabled(name, enabled)
                    if ok:
                        await _send(ws, "status", f"Tool '{name}' {'enabled' if enabled else 'disabled'}.")
                    else:
                        await _send(ws, "error", f"Unknown tool: {name}")
            elif msg_type == "clear":
                if agent:
                    agent.clear_conversation()
                await _send(ws, "status", "Conversation cleared.")
    except WebSocketDisconnect:
        logger.info("Client disconnected")
        if ws is _active_ws:
            _active_ws = None
    except Exception:
        logger.exception("WebSocket error")


async def _handle_config(ws: WebSocket, data: dict) -> None:
    """Apply config updates from the frontend settings panel."""
    updates = data.get("config", {})
    if not updates:
        return

    try:
        model_updates = updates.get("model", {})

        # Reject old-format config (has generic api_key but no per-provider keys).
        # This prevents stale tabs from overriding the active config.
        has_provider_keys = any(
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
        await _send(ws, "status", "Settings updated.")
    except Exception as e:
        logger.exception("Failed to update config")
        await _send(ws, "error", f"Failed to update settings: {e}")


async def _handle_message(ws: WebSocket, data: dict) -> None:
    """Process a user chat message through the agent."""
    content = data.get("content", "").strip()
    if not content:
        return

    if not agent:
        await _send(ws, "error", "Agent not initialized.")
        return

    config = get_config()
    active_key = config.model.get_active_key()
    if not active_key or active_key == "your-api-key-here":
        await _send(
            ws,
            "error",
            "Please set your API key in the settings panel (click the gear icon).",
        )
        return

    # Send typing indicator
    await _send(ws, "typing", "")

    try:
        async for event in agent.process_message(content):
            etype = event["type"]
            if etype == "text":
                await _send(ws, "message", event["content"], role="assistant")
            elif etype == "tool_start":
                await _send(
                    ws,
                    "status",
                    f"Using tool: {event['name']}...",
                    metadata={"tool": event["name"], "arguments": event["arguments"]},
                )
            elif etype == "tool_result":
                await _send(
                    ws,
                    "tool_result",
                    event["result"],
                    metadata={"tool": event["name"]},
                )
            elif etype == "error":
                await _send(ws, "error", event["content"])
            elif etype == "usage":
                await _send(
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
                await _send(ws, "done", "")
    except Exception as e:
        logger.exception("Error processing message")
        await _send(ws, "error", f"Something went wrong: {e}")


async def _send(
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


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> JSONResponse:
    """Handle file uploads from the chat UI."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = Path(file.filename).name if file.filename else "upload"
    # Add timestamp to avoid collisions
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = UPLOAD_DIR / f"{ts}_{safe_name}"

    content = await file.read()
    dest.write_bytes(content)

    size_kb = len(content) / 1024
    logger.info("File uploaded: %s (%.1f KB)", dest.name, size_kb)

    return JSONResponse({
        "status": "ok",
        "filename": dest.name,
        "path": str(dest),
        "size": len(content),
    })


# Mount static files last so the WebSocket route takes precedence
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def main() -> None:
    """Entry point for `python -m chat.server`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    config = get_config()
    uvicorn.run(
        "chat.server:app",
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
