"""Tests for core.config."""

from pathlib import Path

import pytest

from core.config import Config, load_config, ModelConfig


def test_default_config():
    """Default config should have sensible values."""
    config = Config()
    assert config.model.provider == "openai"
    assert config.model.max_tokens == 4096
    assert config.server.port == 8765
    assert config.safety.require_confirmation is True


def test_load_config_missing_file():
    """Loading from a non-existent file should return defaults."""
    config = load_config(Path("/nonexistent/config.yaml"))
    assert config.model.provider == "openai"


def test_load_config_example(tmp_path):
    """Loading from example config should work."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "model:\n"
        "  provider: anthropic\n"
        "  api_key: test-key\n"
        "  model_name: claude-sonnet-4-20250514\n"
        "server:\n"
        "  port: 9000\n"
    )
    config = load_config(config_file)
    assert config.model.provider == "anthropic"
    assert config.model.api_key == "test-key"
    assert config.server.port == 9000
