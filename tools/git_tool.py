"""Git tool — version control operations via git CLI + GitHub API.

All git commands run via subprocess for maximum compatibility.
GitHub API operations use httpx (extracted to git_github.py).
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from tools.base import BaseTool
from tools.git_github import create_github_repo, create_pull_request

logger = logging.getLogger(__name__)


class GitTool(BaseTool):
    """Git version control operations."""

    name = "git"
    description = (
        "Perform Git operations: clone repos, check status, view diffs, "
        "stage and commit changes, push, pull, manage branches, view log."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "git_clone",
                    "git_status",
                    "git_diff",
                    "git_commit",
                    "git_push",
                    "git_pull",
                    "git_branch",
                    "git_log",
                    "git_init",
                    "create_github_repo",
                    "create_pull_request",
                ],
                "description": "The Git action to perform",
            },
            "repo_url": {
                "type": "string",
                "description": "Repository URL (for git_clone)",
            },
            "path": {
                "type": "string",
                "description": "Local repository path (defaults to current dir)",
            },
            "message": {
                "type": "string",
                "description": "Commit message (for git_commit)",
            },
            "branch": {
                "type": "string",
                "description": "Branch name (for git_branch, git_push)",
            },
            "files": {
                "type": "string",
                "description": "Files to stage, space-separated, or '.' for all (for git_commit)",
            },
            "limit": {
                "type": "integer",
                "description": "Number of log entries (for git_log, default 10)",
            },
            "repo_name": {
                "type": "string",
                "description": "Repository name (for create_github_repo, create_pull_request)",
            },
            "private": {
                "type": "boolean",
                "description": "Make repo private (for create_github_repo, default false)",
            },
            "title": {
                "type": "string",
                "description": "PR title (for create_pull_request)",
            },
            "body": {
                "type": "string",
                "description": "PR body/description (for create_pull_request)",
            },
            "base_branch": {
                "type": "string",
                "description": "Base branch for PR (default 'main')",
            },
            "head_branch": {
                "type": "string",
                "description": "Head branch for PR (current branch if empty)",
            },
            "github_token": {
                "type": "string",
                "description": "GitHub personal access token (or set GITHUB_TOKEN env var)",
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")
        path = kwargs.get("path", ".")

        try:
            if action == "git_clone":
                return await self._clone(kwargs.get("repo_url", ""), path)
            elif action == "git_init":
                return await self._run_git("init", cwd=path)
            elif action == "git_status":
                return await self._run_git("status", cwd=path)
            elif action == "git_diff":
                return await self._run_git("diff", cwd=path)
            elif action == "git_commit":
                return await self._commit(
                    path, kwargs.get("message", ""), kwargs.get("files", "."),
                )
            elif action == "git_push":
                branch = kwargs.get("branch", "")
                cmd = f"push origin {branch}" if branch else "push"
                return await self._run_git(cmd, cwd=path)
            elif action == "git_pull":
                return await self._run_git("pull", cwd=path)
            elif action == "git_branch":
                branch = kwargs.get("branch", "")
                if branch:
                    return await self._run_git(f"checkout -b {branch}", cwd=path)
                else:
                    return await self._run_git("branch -a", cwd=path)
            elif action == "git_log":
                limit = kwargs.get("limit", 10)
                return await self._run_git(f"log --oneline -n {limit}", cwd=path)
            elif action == "create_github_repo":
                return await create_github_repo(
                    kwargs.get("repo_name", ""), kwargs.get("private", False),
                    kwargs.get("github_token", ""), path, self._run_git,
                )
            elif action == "create_pull_request":
                return await create_pull_request(
                    kwargs.get("repo_name", ""), kwargs.get("title", ""),
                    kwargs.get("body", ""), kwargs.get("base_branch", "main"),
                    kwargs.get("head_branch", ""), kwargs.get("github_token", ""),
                    path, self._run_git,
                )
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Git action failed: %s", action)
            return f"Git error: {e}"

    async def _clone(self, url: str, path: str) -> str:
        if not url:
            return "Error: repo_url is required for git_clone."
        dest = Path(path).expanduser()
        return await self._run_git(f"clone {url} {dest}")

    async def _commit(self, path: str, message: str, files: str) -> str:
        if not message:
            return "Error: message is required for git_commit."
        files = files or "."
        stage_result = await self._run_git(f"add {files}", cwd=path)
        if "error" in stage_result.lower() or "fatal" in stage_result.lower():
            return f"Failed to stage files:\n{stage_result}"
        return await self._run_git(f'commit -m "{message}"', cwd=path)

    async def _run_git(self, args: str, cwd: str = ".") -> str:
        """Run a git command and return output."""
        cwd_path = Path(cwd).expanduser().resolve()
        cmd = f"git {args}"

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd_path) if cwd_path.exists() else None,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        except asyncio.TimeoutError:
            return f"Git command timed out: {cmd}"

        output = ""
        if stdout:
            output += stdout.decode("utf-8", errors="replace")
        if stderr:
            err = stderr.decode("utf-8", errors="replace")
            if err.strip():
                output += "\n" + err

        if len(output) > 10000:
            output = output[:10000] + "\n... [truncated]"

        return f"$ {cmd}\n{output.strip()}"
