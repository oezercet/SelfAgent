"""Code writer tool — write, run, debug code and manage packages.

Supports any language installed on the system. Executes code safely
with timeouts and output capture.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from tools.base import BaseTool
from tools.code_templates import SCAFFOLD_REGISTRY

logger = logging.getLogger(__name__)

HOME_DIR = Path.home()

# Map language to execution command
RUNNERS = {
    "python": "python3",
    "python3": "python3",
    "javascript": "node",
    "js": "node",
    "node": "node",
    "typescript": "npx ts-node",
    "ts": "npx ts-node",
    "bash": "bash",
    "sh": "sh",
    "ruby": "ruby",
    "php": "php",
    "go": "go run",
    "rust": "rustc -o /tmp/selfagent_rust_out",  # compile step
    "java": "java",
    "perl": "perl",
}

EXTENSIONS = {
    "python": ".py",
    "python3": ".py",
    "javascript": ".js",
    "js": ".js",
    "node": ".js",
    "typescript": ".ts",
    "ts": ".ts",
    "bash": ".sh",
    "sh": ".sh",
    "ruby": ".rb",
    "php": ".php",
    "go": ".go",
    "rust": ".rs",
    "java": ".java",
    "perl": ".pl",
    "html": ".html",
    "css": ".css",
}

PACKAGE_MANAGERS = {
    "pip": "pip install",
    "pip3": "pip3 install",
    "npm": "npm install",
    "yarn": "yarn add",
    "brew": "brew install",
    "gem": "gem install",
    "cargo": "cargo add",
}


class CodeWriterTool(BaseTool):
    """Write, run, and debug code in any language."""

    name = "code_writer"
    description = (
        "Write code to files, execute scripts, debug errors, install packages, "
        "and create project scaffolds. Supports Python, JavaScript, TypeScript, "
        "Bash, Ruby, PHP, Go, Rust, and more."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "write_code",
                    "run_code",
                    "run_inline",
                    "debug_code",
                    "install_package",
                    "create_project",
                ],
                "description": "The code action to perform",
            },
            "language": {
                "type": "string",
                "description": "Programming language (python, javascript, bash, etc.)",
            },
            "code": {
                "type": "string",
                "description": "Source code (for write_code, run_inline)",
            },
            "file_path": {
                "type": "string",
                "description": "File path (for write_code, run_code)",
            },
            "package_name": {
                "type": "string",
                "description": "Package to install (for install_package)",
            },
            "manager": {
                "type": "string",
                "description": "Package manager: pip, npm, yarn, brew (for install_package)",
            },
            "project_name": {
                "type": "string",
                "description": "Project name (for create_project)",
            },
            "project_type": {
                "type": "string",
                "description": "Template: python-script, python-api, html-site, node-api, react-app, wordpress-theme, chrome-extension",
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            if action == "write_code":
                return self._write_code(
                    kwargs.get("file_path", ""),
                    kwargs.get("code", ""),
                    kwargs.get("language", ""),
                )
            elif action == "run_code":
                return await self._run_code(kwargs.get("file_path", ""))
            elif action == "run_inline":
                return await self._run_inline(
                    kwargs.get("language", "python"),
                    kwargs.get("code", ""),
                )
            elif action == "debug_code":
                return await self._run_code(kwargs.get("file_path", ""))
            elif action == "install_package":
                return await self._install_package(
                    kwargs.get("package_name", ""),
                    kwargs.get("manager", "pip"),
                )
            elif action == "create_project":
                return self._create_project(
                    kwargs.get("project_name", ""),
                    kwargs.get("project_type", "python-script"),
                )
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Code writer failed: %s", action)
            return f"Error: {e}"

    def _write_code(self, file_path: str, code: str, language: str) -> str:
        if not file_path:
            return "Error: file_path is required."
        if not code:
            return "Error: code is required."

        path = Path(file_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")

        # Make shell scripts executable
        if language in ("bash", "sh") or path.suffix in (".sh", ".bash"):
            os.chmod(path, 0o755)

        return f"Written {len(code)} chars to {path}"

    async def _run_code(self, file_path: str) -> str:
        if not file_path:
            return "Error: file_path is required."

        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"File not found: {path}"

        # Detect language from extension
        ext = path.suffix.lower()
        lang_map = {v: k for k, v in EXTENSIONS.items()}
        language = lang_map.get(ext, "")
        runner = RUNNERS.get(language)

        if not runner:
            return f"Don't know how to run {ext} files. Supported: {', '.join(set(EXTENSIONS.values()))}"

        cmd = f"{runner} {path}"

        return await self._execute_command(cmd, cwd=str(path.parent))

    async def _run_inline(self, language: str, code: str) -> str:
        if not code:
            return "Error: code is required."

        language = language.lower()

        if language in ("python", "python3"):
            cmd = f"python3 -c {self._shell_quote(code)}"
        elif language in ("javascript", "js", "node"):
            cmd = f"node -e {self._shell_quote(code)}"
        elif language in ("bash", "sh"):
            cmd = f"bash -c {self._shell_quote(code)}"
        elif language == "ruby":
            cmd = f"ruby -e {self._shell_quote(code)}"
        elif language == "php":
            cmd = f"php -r {self._shell_quote(code)}"
        elif language == "perl":
            cmd = f"perl -e {self._shell_quote(code)}"
        else:
            return f"Inline execution not supported for '{language}'. Write to a file first."

        return await self._execute_command(cmd)

    async def _install_package(self, package: str, manager: str) -> str:
        if not package:
            return "Error: package_name is required."

        manager = manager.lower()
        cmd_prefix = PACKAGE_MANAGERS.get(manager)
        if not cmd_prefix:
            return f"Unknown package manager: {manager}. Supported: {', '.join(PACKAGE_MANAGERS.keys())}"

        cmd = f"{cmd_prefix} {package}"
        return await self._execute_command(cmd, timeout=120)

    def _create_project(self, name: str, project_type: str) -> str:
        if not name:
            return "Error: project_name is required."

        base = HOME_DIR / name
        if base.exists():
            return f"Directory already exists: {base}"

        project_type = project_type.lower()

        scaffold_fn = SCAFFOLD_REGISTRY.get(project_type)
        if scaffold_fn is None:
            return (
                f"Unknown template: {project_type}. Available: "
                + ", ".join(SCAFFOLD_REGISTRY.keys())
            )
        return scaffold_fn(base, name)

    # ── Helpers ───────────────────────────────────────

    async def _execute_command(
        self, cmd: str, cwd: str | None = None, timeout: int = 60
    ) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or str(HOME_DIR),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return f"Command timed out after {timeout}s: {cmd}"

        output = ""
        if stdout:
            output += stdout.decode("utf-8", errors="replace")
        if stderr:
            output += "\n[STDERR]\n" + stderr.decode("utf-8", errors="replace")

        if len(output) > 10000:
            output = output[:10000] + "\n... [truncated]"

        return f"$ {cmd}\nExit code: {proc.returncode}\n\n{output.strip()}"

    @staticmethod
    def _shell_quote(s: str) -> str:
        import shlex
        return shlex.quote(s)
