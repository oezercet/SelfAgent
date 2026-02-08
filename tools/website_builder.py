"""Website builder tool -- create, preview, deploy, and edit websites.

Generates complete websites from templates, starts local preview
servers, deploys to hosting, and edits existing sites.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from tools.base import BaseTool
from tools.website_builder_ops import add_page, deploy_website, optimize_website
from tools.website_templates import TEMPLATES as _TEMPLATES_BASE
from tools.website_templates_extra import TEMPLATES_EXTRA as _TEMPLATES_EXTRA
from tools.website_templates_more import TEMPLATES_MORE as _TEMPLATES_MORE

logger = logging.getLogger(__name__)

HOME_DIR = Path.home()

# Merge all template sets into one dict
TEMPLATES: dict[str, dict] = {**_TEMPLATES_BASE, **_TEMPLATES_EXTRA, **_TEMPLATES_MORE}


class WebsiteBuilderTool(BaseTool):
    """Generate complete websites from templates."""

    name = "website_builder"
    description = (
        "Create complete websites from templates (landing page, portfolio, dashboard), "
        "start local preview servers, and edit existing site files. "
        "All sites are mobile responsive with clean HTML/CSS."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "create_website",
                    "preview_website",
                    "edit_file",
                    "list_templates",
                    "deploy_website",
                    "add_page",
                    "optimize_website",
                ],
                "description": "The action to perform",
            },
            "template": {
                "type": "string",
                "description": "Template: landing, portfolio, dashboard, blog, e-commerce, documentation, restaurant, saas-landing",
            },
            "project_path": {
                "type": "string",
                "description": "Path for the website project",
            },
            "name": {
                "type": "string",
                "description": "Website/project name",
            },
            "description": {
                "type": "string",
                "description": "Website description",
            },
            "file_path": {
                "type": "string",
                "description": "File to edit (for edit_file)",
            },
            "content": {
                "type": "string",
                "description": "New file content (for edit_file)",
            },
            "port": {
                "type": "integer",
                "description": "Port for preview server (default 8000)",
            },
            "platform": {
                "type": "string",
                "enum": ["netlify", "github-pages"],
                "description": "Deployment platform (for deploy_website)",
            },
            "page_name": {
                "type": "string",
                "description": "Page name e.g. 'about', 'contact' (for add_page)",
            },
            "page_title": {
                "type": "string",
                "description": "Page title (for add_page)",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._preview_processes: dict[str, asyncio.subprocess.Process] = {}

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            if action == "create_website":
                return self._create_website(
                    kwargs.get("template", "landing"),
                    kwargs.get("project_path", ""),
                    kwargs.get("name", "My Website"),
                    kwargs.get("description", "A beautiful website"),
                )
            elif action == "preview_website":
                return await self._preview(
                    kwargs.get("project_path", ""),
                    kwargs.get("port", 8000),
                )
            elif action == "edit_file":
                return self._edit_file(
                    kwargs.get("file_path", ""),
                    kwargs.get("content", ""),
                )
            elif action == "list_templates":
                return self._list_templates()
            elif action == "deploy_website":
                return await deploy_website(
                    kwargs.get("project_path", ""),
                    kwargs.get("platform", "netlify"),
                )
            elif action == "add_page":
                return add_page(
                    kwargs.get("project_path", ""),
                    kwargs.get("page_name", ""),
                    kwargs.get("page_title", ""),
                    kwargs.get("content", ""),
                    kwargs.get("name", "My Website"),
                )
            elif action == "optimize_website":
                return optimize_website(kwargs.get("project_path", ""))
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Website builder error: %s", action)
            return f"Error: {e}"

    def _create_website(
        self, template: str, project_path: str, name: str, description: str
    ) -> str:
        if not project_path:
            return "Error: project_path is required."

        tpl = TEMPLATES.get(template)
        if not tpl:
            available = ", ".join(TEMPLATES.keys())
            return f"Unknown template '{template}'. Available: {available}"

        base = Path(project_path).expanduser()
        if base.exists():
            return f"Directory already exists: {base}"

        base.mkdir(parents=True)

        for filename, content in tpl["files"].items():
            rendered = content.format(name=name, description=description)
            (base / filename).write_text(rendered, encoding="utf-8")

        files = list(tpl["files"].keys())
        return (
            f"Created '{template}' website at {base}\n"
            f"Files: {', '.join(files)}\n\n"
            f"Preview with: action=preview_website, project_path={base}"
        )

    async def _preview(self, project_path: str, port: int) -> str:
        if not project_path:
            return "Error: project_path is required."

        path = Path(project_path).expanduser().resolve()
        if not path.exists():
            return f"Directory not found: {path}"

        # Stop existing preview on same port
        key = str(port)
        if key in self._preview_processes:
            self._preview_processes[key].kill()

        proc = await asyncio.create_subprocess_exec(
            "python3", "-m", "http.server", str(port),
            cwd=str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._preview_processes[key] = proc

        return f"Preview server started at http://localhost:{port}\nServing: {path}"

    def _edit_file(self, file_path: str, content: str) -> str:
        if not file_path:
            return "Error: file_path is required."
        if not content:
            return "Error: content is required."

        path = Path(file_path).expanduser()
        if not path.exists():
            return f"File not found: {path}"

        path.write_text(content, encoding="utf-8")
        return f"Updated {path} ({len(content)} chars)"

    def _list_templates(self) -> str:
        lines = ["Available website templates:\n"]
        for name, tpl in TEMPLATES.items():
            lines.append(f"  - {name}: {tpl['description']}")
        return "\n".join(lines)
