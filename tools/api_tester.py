"""API tester tool — send HTTP requests and test endpoints.

Like a built-in Postman. Supports all HTTP methods with
headers, body, and response assertions.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from tools.base import BaseTool

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "storage"


class ApiTesterTool(BaseTool):
    """Test REST APIs with HTTP requests."""

    name = "api_tester"
    description = (
        "Send HTTP requests to test APIs. Supports GET, POST, PUT, PATCH, DELETE "
        "with custom headers and JSON body. Can assert response status and save "
        "request collections."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["api_request", "test_endpoint", "save_collection", "load_collection", "generate_docs"],
                "description": "The API testing action",
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                "description": "HTTP method",
            },
            "url": {
                "type": "string",
                "description": "Request URL",
            },
            "headers": {
                "type": "object",
                "description": "Request headers as key-value pairs",
            },
            "body": {
                "type": "string",
                "description": "Request body (JSON string)",
            },
            "expected_status": {
                "type": "integer",
                "description": "Expected HTTP status code (for test_endpoint)",
            },
            "collection_name": {
                "type": "string",
                "description": "Collection name (for save_collection)",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._history: list[dict] = []

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            if action == "api_request":
                return await self._request(kwargs)
            elif action == "test_endpoint":
                return await self._test_endpoint(kwargs)
            elif action == "save_collection":
                return self._save_collection(kwargs.get("collection_name", ""))
            elif action == "load_collection":
                return self._load_collection(kwargs.get("collection_name", ""))
            elif action == "generate_docs":
                return self._generate_docs(kwargs.get("collection_name", ""))
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("API tester error: %s", action)
            return f"API error: {e}"

    async def _request(self, kwargs: dict) -> str:
        method = kwargs.get("method", "GET").upper()
        url = kwargs.get("url", "")
        headers = kwargs.get("headers") or {}
        body_str = kwargs.get("body", "")

        if not url:
            return "Error: url is required."

        # Parse body
        body = None
        if body_str:
            try:
                body = json.loads(body_str)
            except json.JSONDecodeError:
                body = body_str

        start = time.time()
        resp = await self._client.request(
            method, url, headers=headers, json=body if isinstance(body, dict) else None,
            content=body if isinstance(body, str) else None,
        )
        elapsed = time.time() - start

        # Store in history
        self._history.append({
            "method": method, "url": url, "status": resp.status_code,
            "time": round(elapsed, 3),
        })

        # Format response
        try:
            resp_body = json.dumps(resp.json(), indent=2)
        except Exception:
            resp_body = resp.text[:5000]

        resp_headers = "\n".join(f"  {k}: {v}" for k, v in resp.headers.items())

        return (
            f"{method} {url}\n"
            f"Status: {resp.status_code} ({elapsed:.3f}s)\n\n"
            f"Response Headers:\n{resp_headers}\n\n"
            f"Response Body:\n{resp_body}"
        )

    async def _test_endpoint(self, kwargs: dict) -> str:
        method = kwargs.get("method", "GET").upper()
        url = kwargs.get("url", "")
        expected_status = kwargs.get("expected_status", 200)

        if not url:
            return "Error: url is required."

        headers = kwargs.get("headers") or {}
        body_str = kwargs.get("body", "")
        body = None
        if body_str:
            try:
                body = json.loads(body_str)
            except json.JSONDecodeError:
                body = body_str

        start = time.time()
        resp = await self._client.request(
            method, url, headers=headers, json=body if isinstance(body, dict) else None,
            content=body if isinstance(body, str) else None,
        )
        elapsed = time.time() - start

        passed = resp.status_code == expected_status
        status_icon = "PASS" if passed else "FAIL"

        result = (
            f"[{status_icon}] {method} {url}\n"
            f"  Expected: {expected_status}, Got: {resp.status_code} ({elapsed:.3f}s)"
        )

        if not passed:
            try:
                result += f"\n  Body: {json.dumps(resp.json())[:500]}"
            except Exception:
                result += f"\n  Body: {resp.text[:500]}"

        return result

    def _save_collection(self, name: str) -> str:
        if not name:
            return "Error: collection_name is required."
        if not self._history:
            return "No requests in history to save."

        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        path = STORAGE_DIR / f"api_collection_{name}.json"
        path.write_text(
            json.dumps(self._history, indent=2), encoding="utf-8"
        )
        return f"Saved {len(self._history)} requests to {path}"

    def _load_collection(self, name: str) -> str:
        """Load a previously saved request collection."""
        if not name:
            return "Error: collection_name is required."

        path = STORAGE_DIR / f"api_collection_{name}.json"
        if not path.exists():
            # List available collections
            available = list(STORAGE_DIR.glob("api_collection_*.json"))
            if available:
                names = [p.stem.replace("api_collection_", "") for p in available]
                return f"Collection '{name}' not found. Available: {', '.join(names)}"
            return f"Collection '{name}' not found. No saved collections."

        data = json.loads(path.read_text(encoding="utf-8"))
        self._history = data

        lines = [f"Loaded collection '{name}' ({len(data)} requests):"]
        for i, req in enumerate(data, 1):
            lines.append(f"  {i}. {req.get('method', '?')} {req.get('url', '?')} -> {req.get('status', '?')} ({req.get('time', '?')}s)")
        return "\n".join(lines)

    def _generate_docs(self, name: str) -> str:
        """Generate API documentation from request history or a saved collection."""
        history = self._history

        if name:
            path = STORAGE_DIR / f"api_collection_{name}.json"
            if path.exists():
                history = json.loads(path.read_text(encoding="utf-8"))

        if not history:
            return "Error: No requests in history. Make some API requests first or load a collection."

        # Group endpoints by base URL
        from urllib.parse import urlparse
        endpoints: dict[str, list[dict]] = {}
        for req in history:
            url = req.get("url", "")
            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            path_str = parsed.path or "/"
            key = f"{req.get('method', 'GET')} {path_str}"
            endpoints.setdefault(base, []).append({
                "method": req.get("method", "GET"),
                "path": path_str,
                "status": req.get("status", "?"),
                "time": req.get("time", "?"),
            })

        lines = ["# API Documentation\n"]
        for base_url, reqs in endpoints.items():
            lines.append(f"## Base URL: `{base_url}`\n")
            seen = set()
            for r in reqs:
                key = f"{r['method']} {r['path']}"
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"### `{r['method']}` `{r['path']}`\n")
                lines.append(f"- **Status**: {r['status']}")
                lines.append(f"- **Response time**: {r['time']}s\n")

        doc = "\n".join(lines)

        # Save docs
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        doc_name = name or "api_docs"
        doc_path = STORAGE_DIR / f"{doc_name}_docs.md"
        doc_path.write_text(doc, encoding="utf-8")

        return f"Generated API documentation ({len(endpoints)} base URL(s), saved to {doc_path}):\n\n{doc}"
