"""Plugin loader — discover and load custom tools from the plugins directory.

Each plugin is a Python file containing a class that extends BaseTool.
The loader finds all BaseTool subclasses in the plugins/ directory and
registers them with the tool registry.
"""

import importlib.util
import logging
from pathlib import Path
from typing import Any

from tools.base import BaseTool
from tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"


def discover_plugins(plugins_dir: Path | None = None) -> list[type[BaseTool]]:
    """Discover BaseTool subclasses in the plugins directory."""
    directory = plugins_dir or PLUGINS_DIR
    if not directory.exists():
        logger.info("No plugins directory found at %s", directory)
        return []

    plugins: list[type[BaseTool]] = []

    for py_file in sorted(directory.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        try:
            spec = importlib.util.spec_from_file_location(
                f"plugins.{py_file.stem}", py_file
            )
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find all BaseTool subclasses in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseTool)
                    and attr is not BaseTool
                    and hasattr(attr, "name")
                    and attr.name
                ):
                    plugins.append(attr)
                    logger.info("Discovered plugin: %s from %s", attr.name, py_file.name)

        except Exception:
            logger.exception("Failed to load plugin from %s", py_file.name)

    return plugins


def load_plugins(registry: ToolRegistry, plugins_dir: Path | None = None) -> int:
    """Load and register all plugins found in the plugins directory.

    Returns the number of plugins successfully loaded.
    """
    plugin_classes = discover_plugins(plugins_dir)
    loaded = 0

    for cls in plugin_classes:
        try:
            instance = cls()
            registry.register(instance)
            loaded += 1
        except Exception:
            logger.exception("Failed to instantiate plugin: %s", cls.__name__)

    if loaded:
        logger.info("Loaded %d plugin(s)", loaded)
    return loaded
