"""Tests for core.agent."""

import pytest

from core.agent import Agent
from core.memory import Memory
from core.model_router import AgentResponse, ModelRouter
from core.task_manager import TaskManager
from tools.registry import ToolRegistry


class MockRouter:
    """Mock ModelRouter that returns a fixed response."""

    def __init__(self, text: str = "Hello!", input_tokens: int = 10, output_tokens: int = 5) -> None:
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    async def chat(self, messages, tools=None, system_prompt=""):
        return AgentResponse(
            text=self.text,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )

    async def close(self):
        pass


class MockTaskManager:
    """Mock TaskManager for tests."""

    async def format_active_tasks(self):
        return "No active tasks."


class MockMemory:
    """Mock Memory for tests."""

    def __init__(self):
        self._messages = []

    def add(self, role, content, metadata=None):
        self._messages.append({"role": role, "content": content})

    def get_messages(self):
        return list(self._messages)

    def clear(self):
        self._messages.clear()

    async def save_message(self, role, content, metadata=None):
        pass

    async def search_relevant(self, query, top_k=5):
        return []

    async def get_user_profile(self):
        return {}

    async def get_message_count(self):
        return len(self._messages)


@pytest.mark.asyncio
async def test_agent_basic_response():
    """Agent should return model's text response."""
    router = MockRouter("Test response")
    agent = Agent(
        model_router=router,
        tool_registry=ToolRegistry(),
        memory=MockMemory(),
        task_manager=MockTaskManager(),
    )

    events = []
    async for event in agent.process_message("Hello"):
        events.append(event)

    text_events = [e for e in events if e["type"] == "text"]
    assert len(text_events) == 1
    assert text_events[0]["content"] == "Test response"


@pytest.mark.asyncio
async def test_agent_done_event():
    """Agent should yield a done event after processing."""
    router = MockRouter("Done")
    agent = Agent(
        model_router=router,
        tool_registry=ToolRegistry(),
        memory=MockMemory(),
        task_manager=MockTaskManager(),
    )

    events = []
    async for event in agent.process_message("Hi"):
        events.append(event)

    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_agent_saves_to_memory():
    """Agent should save messages to memory."""
    mem = MockMemory()
    router = MockRouter("Response")
    agent = Agent(
        model_router=router,
        tool_registry=ToolRegistry(),
        memory=mem,
        task_manager=MockTaskManager(),
    )

    async for _ in agent.process_message("Hello"):
        pass

    messages = mem.get_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_agent_usage_tracking():
    """Agent should emit usage events with token counts."""
    router = MockRouter("Response", input_tokens=100, output_tokens=50)
    agent = Agent(
        model_router=router,
        tool_registry=ToolRegistry(),
        memory=MockMemory(),
        task_manager=MockTaskManager(),
    )

    events = []
    async for event in agent.process_message("Hello"):
        events.append(event)

    usage_events = [e for e in events if e["type"] == "usage"]
    assert len(usage_events) == 1
    assert usage_events[0]["input_tokens"] == 100
    assert usage_events[0]["output_tokens"] == 50
    assert usage_events[0]["total_input_tokens"] == 100
    assert usage_events[0]["total_output_tokens"] == 50

    # Second message should accumulate
    async for event in agent.process_message("Again"):
        events.append(event)

    usage_events = [e for e in events if e["type"] == "usage"]
    assert len(usage_events) == 2
    assert usage_events[1]["total_input_tokens"] == 200
    assert usage_events[1]["total_output_tokens"] == 100


@pytest.mark.asyncio
async def test_agent_clear_conversation():
    """Agent clear should reset conversation."""
    mem = MockMemory()
    router = MockRouter("Hi")
    agent = Agent(
        model_router=router,
        tool_registry=ToolRegistry(),
        memory=mem,
        task_manager=MockTaskManager(),
    )

    async for _ in agent.process_message("Hello"):
        pass

    assert len(agent.conversation) > 0
    agent.clear_conversation()
    assert len(agent.conversation) == 0
