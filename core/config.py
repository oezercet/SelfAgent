"""Configuration loader for SelfAgent."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
EXAMPLE_CONFIG_PATH = Path(__file__).parent.parent / "config.example.yaml"


@dataclass
class ModelConfig:
    provider: str = "openai"
    api_key: str = ""
    model_name: str = "gpt-4o"
    base_url: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    # Per-provider API keys
    openai_key: str = ""
    anthropic_key: str = ""
    google_key: str = ""
    openrouter_key: str = ""

    def get_active_key(self) -> str:
        """Return the API key for the current provider."""
        provider_keys = {
            "openai": self.openai_key,
            "anthropic": self.anthropic_key,
            "google": self.google_key,
            "openrouter": self.openrouter_key,
        }
        # Per-provider key takes priority, fallback to generic api_key
        return provider_keys.get(self.provider, "") or self.api_key


@dataclass
class MemoryConfig:
    max_short_term: int = 50
    vector_db: bool = True
    auto_summarize: bool = True


@dataclass
class EmailConfig:
    enabled: bool = False
    imap_server: str = ""
    smtp_server: str = ""
    email: str = ""
    password: str = ""


@dataclass
class BrowserConfig:
    headless: bool = True
    timeout: int = 30


@dataclass
class SafetyConfig:
    require_confirmation: bool = True
    blocked_commands: list[str] = field(
        default_factory=lambda: ["rm -rf /", "format", "mkfs"]
    )
    max_file_size_mb: int = 100


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = True


@dataclass
class Config:
    """Application configuration."""

    model: ModelConfig = field(default_factory=ModelConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


def _dict_to_dataclass(cls: type, data: dict[str, Any]) -> Any:
    """Convert a dict to a dataclass, ignoring unknown fields."""
    if not data:
        return cls()
    valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in valid_fields}
    return cls(**filtered)


def load_config(path: Path | None = None) -> Config:
    """Load configuration from YAML file.

    Falls back to defaults if config file doesn't exist.
    """
    config_path = path or CONFIG_PATH

    if not config_path.exists():
        logger.warning(
            "Config file not found at %s. Using defaults. "
            "Copy config.example.yaml to config.yaml and add your API key.",
            config_path,
        )
        return Config()

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    return Config(
        model=_dict_to_dataclass(ModelConfig, raw.get("model", {})),
        memory=_dict_to_dataclass(MemoryConfig, raw.get("memory", {})),
        email=_dict_to_dataclass(EmailConfig, raw.get("email", {})),
        browser=_dict_to_dataclass(BrowserConfig, raw.get("browser", {})),
        safety=_dict_to_dataclass(SafetyConfig, raw.get("safety", {})),
        server=_dict_to_dataclass(ServerConfig, raw.get("server", {})),
    )


# Singleton config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global config instance, loading it on first access."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> Config:
    """Reload configuration from disk."""
    global _config
    _config = load_config()
    return _config


def update_config_from_dict(updates: dict[str, Any]) -> Config:
    """Update the runtime config from a dict (e.g., from frontend settings).

    Does not persist to disk.
    """
    global _config
    if _config is None:
        _config = load_config()

    for section, values in updates.items():
        if hasattr(_config, section) and isinstance(values, dict):
            section_obj = getattr(_config, section)
            for key, value in values.items():
                if hasattr(section_obj, key):
                    setattr(section_obj, key, value)

    return _config
