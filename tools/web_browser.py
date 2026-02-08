"""Web browser tool — automates browser interactions using Playwright.

Maintains a persistent browser context. Pages are reused when possible.
"""

import logging
from typing import Any

from tools.base import BaseTool
from tools.browser_actions import BrowserActionsMixin
from tools.browser_helpers import BrowserHelpersMixin
from tools.browser_page_actions import BrowserPageActionsMixin

logger = logging.getLogger(__name__)


class WebBrowserTool(BrowserActionsMixin, BrowserPageActionsMixin, BrowserHelpersMixin, BaseTool):
    """Playwright-based web browser automation."""

    name = "web_browser"
    description = (
        "Browse the web: navigate to pages, read content, click elements, "
        "fill forms, press keys, take screenshots, scroll, hover, wait, and run JS. "
        "TIPS: "
        "1) Use 'text=Submit' syntax in selector to click by visible text. "
        "2) Use wait_for before interacting with dynamic elements. "
        "3) For autocomplete: fill the input, use wait_for to wait for dropdown, then click the option. "
        "4) Use evaluate_js for complex interactions that standard actions can't handle. "
        "5) Use hover to reveal hidden menus or tooltips."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "navigate",
                    "click",
                    "fill",
                    "type_text",
                    "press_key",
                    "screenshot",
                    "get_elements",
                    "get_links",
                    "get_text",
                    "scroll",
                    "go_back",
                    "close",
                    "wait_for",
                    "hover",
                    "select_option",
                    "evaluate_js",
                ],
                "description": "The browser action to perform",
            },
            "url": {
                "type": "string",
                "description": "URL to navigate to (for navigate)",
            },
            "selector": {
                "type": "string",
                "description": (
                    "Target element selector. Supports CSS selectors (#id, .class, tag[attr]), "
                    "Playwright text selectors (text=Click me), and aria selectors "
                    "(role=button[name='Submit']). For click, fill, hover, wait_for, etc."
                ),
            },
            "value": {
                "type": "string",
                "description": "Value to type/fill (for fill, type_text, select_option, evaluate_js)",
            },
            "key": {
                "type": "string",
                "description": "Key to press, e.g. 'Enter', 'Tab', 'Escape' (for press_key)",
            },
            "direction": {
                "type": "string",
                "enum": ["up", "down"],
                "description": "Scroll direction (for scroll)",
            },
            "timeout": {
                "type": "integer",
                "description": "Max wait time in seconds (for wait_for, default 10)",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._page = None

    async def execute(self, **kwargs: Any) -> str:
        """Execute a browser action."""
        action = kwargs.get("action", "")

        if action == "close":
            await self.close_browser()
            return "Browser closed."

        try:
            await self._ensure_browser()
        except Exception as e:
            logger.exception("Failed to launch browser")
            return (
                f"Error launching browser: {e}\n"
                "Make sure Playwright is installed: playwright install chromium"
            )

        try:
            if action == "navigate":
                return await self._navigate(kwargs.get("url", ""))
            elif action == "click":
                return await self._click(kwargs.get("selector", ""))
            elif action == "fill":
                return await self._fill(
                    kwargs.get("selector", ""), kwargs.get("value", "")
                )
            elif action == "type_text":
                return await self._type_text(kwargs.get("value", ""))
            elif action == "press_key":
                return await self._press_key(
                    kwargs.get("key", "Enter"), kwargs.get("selector", "")
                )
            elif action == "screenshot":
                return await self._screenshot()
            elif action == "get_elements":
                return await self._get_elements()
            elif action == "get_links":
                return await self._get_links()
            elif action == "get_text":
                return await self._get_text()
            elif action == "scroll":
                return await self._scroll(kwargs.get("direction", "down"))
            elif action == "go_back":
                return await self._go_back()
            elif action == "wait_for":
                return await self._wait_for(
                    kwargs.get("selector", ""), kwargs.get("timeout", 10)
                )
            elif action == "hover":
                return await self._hover(kwargs.get("selector", ""))
            elif action == "select_option":
                return await self._select_option(
                    kwargs.get("selector", ""), kwargs.get("value", "")
                )
            elif action == "evaluate_js":
                return await self._evaluate_js(kwargs.get("value", ""))
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Browser action failed: %s", action)
            return f"Browser error: {e}"
