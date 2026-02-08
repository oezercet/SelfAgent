"""WebSocket chat server for SelfAgent."""

import asyncio
import json
import logging
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from chat.auth import is_auth_enabled, verify_pin, verify_token
from chat.handlers import handle_check_ollama, handle_config, handle_message, handle_pull_ollama, send_ws
from core.agent import Agent
from core.config import get_config
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

    # PIN auth check
    authenticated = not is_auth_enabled()
    session_token = ""

    if not authenticated:
        await send_ws(ws, "auth_required", "PIN required to continue.")

    # Only the most recent connection is the active one
    _active_ws = ws

    try:
        while True:
            raw = await ws.receive_text()

            # If no active connection, promote this one
            if _active_ws is None:
                _active_ws = ws
            # Ignore messages from stale connections
            if ws is not _active_ws:
                logger.info("Ignoring message from stale WebSocket connection")
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await send_ws(ws, "error", "Invalid message format.")
                continue
            msg_type = data.get("type", "message")

            # Handle auth message
            if msg_type == "auth":
                pin = data.get("pin", "")
                token = verify_pin(pin)
                if token:
                    authenticated = True
                    session_token = token
                    await send_ws(ws, "auth_success", "Authenticated.")
                else:
                    await send_ws(ws, "auth_failed", "Wrong PIN.")
                continue

            # Block non-auth messages until authenticated
            if not authenticated:
                await send_ws(ws, "auth_required", "PIN required to continue.")
                continue

            if msg_type == "config":
                # Frontend sending config updates (API key, model, etc.)
                await handle_config(ws, data)
            elif msg_type == "message":
                # Use lock to prevent concurrent processing
                if _processing_lock.locked():
                    await send_ws(ws, "error", "Already processing a message. Please wait.")
                    continue
                async with _processing_lock:
                    await handle_message(ws, data, agent)
            elif msg_type == "get_tools":
                if agent:
                    tools_list = agent.tools.list_tools_with_status()
                    await send_ws(ws, "tools_list", "", metadata={"tools": tools_list})
            elif msg_type == "toggle_tool":
                if agent:
                    name = data.get("tool_name", "")
                    enabled = data.get("enabled", True)
                    ok = agent.tools.set_tool_enabled(name, enabled)
                    if ok:
                        await send_ws(ws, "status", f"Tool '{name}' {'enabled' if enabled else 'disabled'}.")
                    else:
                        await send_ws(ws, "error", f"Unknown tool: {name}")
            elif msg_type == "check_ollama":
                await handle_check_ollama(ws, data)
            elif msg_type == "pull_ollama":
                await handle_pull_ollama(ws, data)
            elif msg_type == "clear":
                if agent:
                    agent.clear_conversation()
                await send_ws(ws, "status", "Conversation cleared.")
    except WebSocketDisconnect:
        logger.info("Client disconnected")
        if ws is _active_ws:
            _active_ws = None
    except Exception:
        logger.exception("WebSocket error")


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
