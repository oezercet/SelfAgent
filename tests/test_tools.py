"""Tests for tools.base, tools.registry, and tools.plugin_loader."""

import tempfile
from pathlib import Path

import pytest

from tools.base import BaseTool
from tools.registry import ToolRegistry


class DummyTool(BaseTool):
    name = "dummy"
    description = "A test tool"
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Input text"},
        },
        "required": ["text"],
    }

    async def execute(self, **kwargs) -> str:
        return f"echo: {kwargs.get('text', '')}"


def test_tool_schema():
    """Tool should produce a valid function schema."""
    tool = DummyTool()
    schema = tool.to_function_schema()
    assert schema["name"] == "dummy"
    assert "properties" in schema["parameters"]


@pytest.mark.asyncio
async def test_tool_execute():
    """Tool execute should return a string result."""
    tool = DummyTool()
    result = await tool.execute(text="hello")
    assert result == "echo: hello"


def test_registry_register_and_list():
    """Registry should register and list tools."""
    reg = ToolRegistry()
    reg.register(DummyTool())
    assert "dummy" in reg.list_tools()


def test_registry_get_schemas():
    """Registry should return schemas for all tools."""
    reg = ToolRegistry()
    reg.register(DummyTool())
    schemas = reg.get_schemas()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "dummy"


@pytest.mark.asyncio
async def test_registry_execute():
    """Registry should execute a tool by name."""
    reg = ToolRegistry()
    reg.register(DummyTool())
    result = await reg.execute("dummy", text="world")
    assert result == "echo: world"


@pytest.mark.asyncio
async def test_registry_execute_unknown():
    """Registry should handle unknown tool gracefully."""
    reg = ToolRegistry()
    result = await reg.execute("nonexistent")
    assert "Unknown tool" in result


# ── Tool enable/disable tests ──────────────────────────

def test_registry_disable_tool():
    """Disabled tools should be excluded from schemas."""
    reg = ToolRegistry()
    reg.register(DummyTool())
    assert len(reg.get_schemas()) == 1

    reg.set_tool_enabled("dummy", False)
    assert len(reg.get_schemas()) == 0


@pytest.mark.asyncio
async def test_registry_disabled_tool_execution():
    """Executing a disabled tool should return an error."""
    reg = ToolRegistry()
    reg.register(DummyTool())
    reg.set_tool_enabled("dummy", False)
    result = await reg.execute("dummy", text="test")
    assert "disabled" in result.lower()


def test_registry_enable_tool():
    """Re-enabling a tool should restore it to schemas."""
    reg = ToolRegistry()
    reg.register(DummyTool())
    reg.set_tool_enabled("dummy", False)
    reg.set_tool_enabled("dummy", True)
    assert len(reg.get_schemas()) == 1


def test_registry_list_tools_with_status():
    """list_tools_with_status should include enabled flag."""
    reg = ToolRegistry()
    reg.register(DummyTool())
    tools = reg.list_tools_with_status()
    assert len(tools) == 1
    assert tools[0]["name"] == "dummy"
    assert tools[0]["enabled"] is True

    reg.set_tool_enabled("dummy", False)
    tools = reg.list_tools_with_status()
    assert tools[0]["enabled"] is False


def test_registry_set_tool_enabled_unknown():
    """set_tool_enabled on unknown tool should return False."""
    reg = ToolRegistry()
    assert reg.set_tool_enabled("unknown", True) is False


# ── Plugin loader tests ────────────────────────────────

def test_plugin_discover():
    """Plugin loader should discover tools in a directory."""
    from tools.plugin_loader import discover_plugins

    plugins_dir = Path(__file__).parent.parent / "plugins"
    plugins = discover_plugins(plugins_dir)
    # Should find at least the example plugin
    names = [p.name for p in plugins]
    assert "hello_world" in names


def test_plugin_load_and_register():
    """Plugin loader should register discovered tools."""
    from tools.plugin_loader import load_plugins

    reg = ToolRegistry()
    plugins_dir = Path(__file__).parent.parent / "plugins"
    count = load_plugins(reg, plugins_dir)
    assert count >= 1
    assert "hello_world" in reg.list_tools()


def test_plugin_discover_empty_dir():
    """Plugin loader should handle empty directory."""
    from tools.plugin_loader import discover_plugins

    with tempfile.TemporaryDirectory() as tmpdir:
        plugins = discover_plugins(Path(tmpdir))
        assert len(plugins) == 0


def test_plugin_discover_nonexistent_dir():
    """Plugin loader should handle nonexistent directory."""
    from tools.plugin_loader import discover_plugins

    plugins = discover_plugins(Path("/nonexistent/path"))
    assert len(plugins) == 0


# ── Phase 5 tool import tests ─────────────────────────

def test_phase5_tools_importable():
    """All Phase 5 tools should be importable."""
    from tools.screenshot import ScreenshotTool
    from tools.system_control import SystemControlTool
    from tools.clipboard import ClipboardTool
    from tools.image_tool import ImageTool
    from tools.pdf_tool import PdfTool
    from tools.data_analyzer import DataAnalyzerTool
    from tools.downloader import DownloaderTool
    from tools.scheduler import SchedulerTool
    from tools.email_tool import EmailTool

    tools = [
        ScreenshotTool(), SystemControlTool(), ClipboardTool(),
        ImageTool(), PdfTool(), DataAnalyzerTool(),
        DownloaderTool(), SchedulerTool(), EmailTool(),
    ]
    for tool in tools:
        assert tool.name
        assert tool.description
        schema = tool.to_function_schema()
        assert schema["name"] == tool.name


def test_all_tools_registerable():
    """All tools should register without errors."""
    from tools.screenshot import ScreenshotTool
    from tools.system_control import SystemControlTool
    from tools.clipboard import ClipboardTool
    from tools.image_tool import ImageTool
    from tools.pdf_tool import PdfTool
    from tools.data_analyzer import DataAnalyzerTool
    from tools.downloader import DownloaderTool
    from tools.scheduler import SchedulerTool
    from tools.email_tool import EmailTool
    from tools.web_search import WebSearchTool
    from tools.file_manager import FileManagerTool
    from tools.terminal import TerminalTool
    from tools.code_writer import CodeWriterTool
    from tools.git_tool import GitTool
    from tools.database_tool import DatabaseTool
    from tools.api_tester import ApiTesterTool
    from tools.website_builder import WebsiteBuilderTool

    reg = ToolRegistry()
    all_tools = [
        WebSearchTool(), FileManagerTool(), TerminalTool(),
        CodeWriterTool(), GitTool(), DatabaseTool(),
        ApiTesterTool(), WebsiteBuilderTool(),
        ScreenshotTool(), SystemControlTool(), ClipboardTool(),
        ImageTool(), PdfTool(), DataAnalyzerTool(),
        DownloaderTool(), SchedulerTool(), EmailTool(),
    ]
    for tool in all_tools:
        reg.register(tool)

    assert len(reg.list_tools()) == 17
    assert len(reg.get_schemas()) == 17
