"""Tests for core.memory."""

import pytest

from core.memory import Memory


def test_memory_add_and_get():
    """Messages should be stored and retrieved."""
    mem = Memory(max_short_term=10)
    mem.add("user", "Hello")
    mem.add("assistant", "Hi there")

    messages = mem.get_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["content"] == "Hi there"


def test_memory_trim():
    """Memory should trim to max_short_term."""
    mem = Memory(max_short_term=3)
    for i in range(5):
        mem.add("user", f"Message {i}")

    messages = mem.get_messages()
    assert len(messages) == 3
    assert messages[0]["content"] == "Message 2"


def test_memory_clear():
    """Clear should remove all messages."""
    mem = Memory()
    mem.add("user", "Hello")
    mem.clear()
    assert len(mem.get_messages()) == 0


def test_memory_get_recent():
    """get_recent should return last N messages."""
    mem = Memory()
    for i in range(10):
        mem.add("user", f"Msg {i}")

    recent = mem.get_recent(3)
    assert len(recent) == 3
    assert recent[0]["content"] == "Msg 7"


@pytest.mark.asyncio
async def test_memory_sqlite_persistence(tmp_path):
    """Messages should persist to SQLite."""
    import core.memory as mem_module

    # Temporarily override DB path
    original_path = mem_module.DB_PATH
    mem_module.STORAGE_DIR = tmp_path
    mem_module.DB_PATH = tmp_path / "test_memory.db"

    try:
        mem = Memory(max_short_term=10)
        await mem.initialize()

        await mem.save_message("user", "Hello")
        await mem.save_message("assistant", "Hi there")

        rows = await mem.load_recent_conversations(limit=10)
        assert len(rows) == 2
        assert rows[0]["role"] == "user"

        await mem.close()
    finally:
        mem_module.DB_PATH = original_path


@pytest.mark.asyncio
async def test_memory_user_profile(tmp_path):
    """User profile should persist."""
    import core.memory as mem_module

    original_path = mem_module.DB_PATH
    mem_module.STORAGE_DIR = tmp_path
    mem_module.DB_PATH = tmp_path / "test_memory.db"

    try:
        mem = Memory()
        await mem.initialize()

        await mem.set_profile("name", "Ozer")
        await mem.set_profile("language", "Turkish")

        profile = await mem.get_user_profile()
        assert profile["name"] == "Ozer"
        assert profile["language"] == "Turkish"

        # Update
        await mem.set_profile("name", "Ozer C")
        name = await mem.get_profile("name")
        assert name == "Ozer C"

        await mem.close()
    finally:
        mem_module.DB_PATH = original_path
