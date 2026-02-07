"""File manager tool — safe file system operations.

All operations are sandboxed to the user's home directory.
Destructive operations (delete, overwrite) require confirmation.
"""

import logging
import shutil
from pathlib import Path
from typing import Any

from core.config import get_config
from tools.base import BaseTool

logger = logging.getLogger(__name__)

HOME_DIR = Path.home()


class FileManagerTool(BaseTool):
    """Manage files and directories safely."""

    name = "file_manager"
    description = (
        f"Perform file operations: list directories, read/write files, "
        f"move, delete, and search. All operations are sandboxed to the "
        f"user's home directory ({HOME_DIR}) for safety. "
        f"Use paths like '{HOME_DIR}/Desktop' or '~/Desktop' or just 'Desktop'."
    )
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "list_directory",
                    "read_file",
                    "write_file",
                    "move_file",
                    "delete_file",
                    "search_files",
                    "file_info",
                    "create_directory",
                ],
                "description": "The file operation to perform",
            },
            "path": {
                "type": "string",
                "description": "File or directory path",
            },
            "content": {
                "type": "string",
                "description": "Content to write (for write_file)",
            },
            "destination": {
                "type": "string",
                "description": "Destination path (for move_file)",
            },
            "query": {
                "type": "string",
                "description": "Search query (for search_files)",
            },
        },
        "required": ["action", "path"],
    }

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve and validate a path within the home directory.

        Accepts absolute paths, ~ paths, or relative paths (resolved
        relative to the user's home directory).
        """
        path_str = path_str.strip()

        # Handle ~ prefix
        if path_str.startswith("~"):
            p = Path(path_str).expanduser().resolve()
        # Handle absolute paths
        elif path_str.startswith("/"):
            p = Path(path_str).resolve()
        # Relative paths → resolve relative to home directory
        else:
            p = (HOME_DIR / path_str).resolve()

        # Sandbox check: must be inside the home directory
        try:
            p.relative_to(HOME_DIR)
        except ValueError:
            raise PermissionError(
                f"Access denied: {p} is outside the home directory ({HOME_DIR})."
            )
        return p

    def _check_file_size(self, path: Path) -> None:
        """Check file size against the configured limit."""
        config = get_config()
        max_bytes = config.safety.max_file_size_mb * 1024 * 1024
        if path.exists() and path.stat().st_size > max_bytes:
            raise ValueError(
                f"File too large: {path.stat().st_size / 1024 / 1024:.1f}MB "
                f"(limit: {config.safety.max_file_size_mb}MB)"
            )

    async def execute(self, **kwargs: Any) -> str:
        """Execute a file operation."""
        action = kwargs.get("action", "")
        path_str = kwargs.get("path", "")

        if not action or not path_str:
            return "Error: action and path are required."

        try:
            path = self._resolve_path(path_str)
        except PermissionError as e:
            return str(e)

        try:
            if action == "list_directory":
                return self._list_directory(path)
            elif action == "read_file":
                return self._read_file(path)
            elif action == "write_file":
                return self._write_file(path, kwargs.get("content", ""))
            elif action == "move_file":
                return self._move_file(path, kwargs.get("destination", ""))
            elif action == "delete_file":
                return self._delete_file(path)
            elif action == "search_files":
                return self._search_files(path, kwargs.get("query", ""))
            elif action == "file_info":
                return self._file_info(path)
            elif action == "create_directory":
                return self._create_directory(path)
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("File operation failed: %s", action)
            return f"Error: {e}"

    def _list_directory(self, path: Path) -> str:
        if not path.exists():
            return f"Directory not found: {path}"
        if not path.is_dir():
            return f"Not a directory: {path}"

        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines = [f"Contents of {path}:\n"]
        for entry in entries[:100]:
            if entry.is_dir():
                lines.append(f"  [DIR]  {entry.name}/")
            else:
                size_str = self._format_size(entry.stat().st_size)
                lines.append(f"  [FILE] {entry.name} ({size_str})")

        total = len(list(path.iterdir()))
        if total > 100:
            lines.append(f"\n  ... and {total - 100} more entries")
        return "\n".join(lines)

    def _read_file(self, path: Path) -> str:
        if not path.exists():
            return f"File not found: {path}"
        if not path.is_file():
            return f"Not a file: {path}"
        self._check_file_size(path)

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Cannot read binary file: {path}"

        if len(content) > 50000:
            return (
                f"File: {path} ({self._format_size(path.stat().st_size)})\n"
                f"Showing first 50000 characters:\n\n"
                f"{content[:50000]}\n\n... [truncated]"
            )
        return f"File: {path}\n\n{content}"

    def _write_file(self, path: Path, content: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Written {len(content)} characters to {path}"

    def _move_file(self, path: Path, dest_str: str) -> str:
        if not dest_str:
            return "Error: destination is required for move_file."
        if not path.exists():
            return f"Source not found: {path}"
        try:
            dest = self._resolve_path(dest_str)
        except PermissionError as e:
            return str(e)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(dest))
        return f"Moved {path} -> {dest}"

    def _delete_file(self, path: Path) -> str:
        if not path.exists():
            return f"Not found: {path}"
        if path.is_dir():
            shutil.rmtree(path)
            return f"Deleted directory: {path}"
        else:
            path.unlink()
            return f"Deleted file: {path}"

    def _search_files(self, path: Path, query: str) -> str:
        if not query:
            return "Error: query is required for search_files."
        if not path.exists() or not path.is_dir():
            return f"Directory not found: {path}"

        matches = []
        try:
            for p in path.rglob(f"*{query}*"):
                if len(matches) >= 50:
                    break
                matches.append(str(p))
        except PermissionError:
            pass

        if not matches:
            return f"No files matching '{query}' found in {path}"
        lines = [f"Files matching '{query}' in {path}:\n"]
        for m in matches:
            lines.append(f"  {m}")
        return "\n".join(lines)

    def _file_info(self, path: Path) -> str:
        if not path.exists():
            return f"Not found: {path}"
        stat = path.stat()
        return "\n".join([
            f"Path: {path}",
            f"Type: {'directory' if path.is_dir() else 'file'}",
            f"Size: {self._format_size(stat.st_size)}",
            f"Permissions: {oct(stat.st_mode)}",
        ])

    def _create_directory(self, path: Path) -> str:
        if path.exists():
            return f"Already exists: {path}"
        path.mkdir(parents=True, exist_ok=True)
        return f"Created directory: {path}"

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f}{unit}" if unit != "B" else f"{size}B"
            size /= 1024
        return f"{size:.1f}TB"
