"""Web search tool — search the internet using DuckDuckGo.

No API key required. Uses the ddgs library.
"""

import logging
from typing import Any

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Search the web using DuckDuckGo."""

    name = "web_search"
    description = (
        "Search the web and return results with titles, URLs, and snippets. "
        "No API key needed. Use this to find information, look up facts, "
        "compare products, find documentation, etc."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default 5, max 20)",
            },
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs: Any) -> str:
        """Perform a web search and return formatted results."""
        query = kwargs.get("query", "")
        max_results = min(kwargs.get("max_results", 5), 20)

        if not query:
            return "Error: No search query provided."

        # Try new ddgs package first, fallback to old duckduckgo_search
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                return "Error: ddgs package not installed. Run: pip install ddgs"

        try:
            results = list(DDGS().text(query, max_results=max_results))

            if not results:
                return f"No results found for: {query}"

            lines = [f"Search results for: {query}\n"]
            for i, r in enumerate(results, 1):
                title = r.get("title", "No title")
                url = r.get("href", r.get("link", ""))
                snippet = r.get("body", r.get("snippet", ""))
                lines.append(f"{i}. {title}")
                lines.append(f"   URL: {url}")
                if snippet:
                    lines.append(f"   {snippet}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            logger.exception("Web search failed")
            return f"Search error: {e}"
