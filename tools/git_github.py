"""GitHub API operations — extracted from git_tool.py."""

import logging
from pathlib import Path
from typing import Any, Callable, Coroutine

import httpx

logger = logging.getLogger(__name__)


def get_github_token(token: str) -> str:
    """Get GitHub token from parameter or environment."""
    if token:
        return token
    import os
    return os.environ.get("GITHUB_TOKEN", "")


async def create_github_repo(
    name: str,
    private: bool,
    token: str,
    path: str,
    run_git: Callable[..., Coroutine[Any, Any, str]],
) -> str:
    """Create a GitHub repository and optionally set it as remote."""
    if not name:
        return "Error: repo_name is required."

    gh_token = get_github_token(token)
    if not gh_token:
        return "Error: GitHub token required. Provide github_token or set GITHUB_TOKEN env var."

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.github.com/user/repos",
            headers={
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "name": name,
                "private": private,
                "auto_init": False,
            },
        )

    if resp.status_code == 201:
        data = resp.json()
        clone_url = data.get("clone_url", "")
        html_url = data.get("html_url", "")

        result = f"Created repository: {html_url}\nClone URL: {clone_url}"

        # Set as remote origin if we're in a git repo
        cwd_path = Path(path).expanduser().resolve()
        git_dir = cwd_path / ".git"
        if git_dir.exists():
            add_remote = await run_git(
                f"remote add origin {clone_url}", cwd=path
            )
            if "fatal" not in add_remote.lower():
                result += f"\nAdded as remote 'origin'"
            else:
                await run_git(
                    f"remote set-url origin {clone_url}", cwd=path
                )
                result += f"\nUpdated remote 'origin'"

        return result
    elif resp.status_code == 422:
        return f"Error: Repository '{name}' already exists or invalid name."
    elif resp.status_code == 401:
        return "Error: Invalid GitHub token."
    else:
        return f"GitHub API error ({resp.status_code}): {resp.text[:500]}"


async def create_pull_request(
    repo_name: str,
    title: str,
    body: str,
    base: str,
    head: str,
    token: str,
    path: str,
    run_git: Callable[..., Coroutine[Any, Any, str]],
) -> str:
    """Create a pull request on GitHub."""
    if not title:
        return "Error: title is required."

    gh_token = get_github_token(token)
    if not gh_token:
        return "Error: GitHub token required. Provide github_token or set GITHUB_TOKEN env var."

    # Detect repo owner/name from remote if not provided
    owner_repo = repo_name
    if not owner_repo or "/" not in owner_repo:
        remote_info = await run_git("remote get-url origin", cwd=path)
        for line in remote_info.split("\n"):
            line = line.strip()
            if "github.com" in line:
                parts = line.rstrip(".git").split("github.com")[-1]
                parts = parts.lstrip("/").lstrip(":")
                if "/" in parts:
                    owner_repo = parts
                    break

    if not owner_repo or "/" not in owner_repo:
        return "Error: Could not detect repo. Provide repo_name as 'owner/repo'."

    # Detect current branch if head not specified
    if not head:
        branch_info = await run_git("rev-parse --abbrev-ref HEAD", cwd=path)
        for line in branch_info.split("\n"):
            line = line.strip()
            if line and not line.startswith("$"):
                head = line
                break

    if not head:
        return "Error: Could not detect current branch. Provide head_branch."

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://api.github.com/repos/{owner_repo}/pulls",
            headers={
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "title": title,
                "body": body or "",
                "head": head,
                "base": base or "main",
            },
        )

    if resp.status_code == 201:
        data = resp.json()
        return (
            f"Pull request created: {data.get('html_url', '')}\n"
            f"#{data.get('number', '?')}: {title}\n"
            f"{head} -> {base}"
        )
    elif resp.status_code == 422:
        error = resp.json()
        errors = error.get("errors", [])
        msg = errors[0].get("message", "") if errors else resp.text[:500]
        return f"Error creating PR: {msg}"
    elif resp.status_code == 401:
        return "Error: Invalid GitHub token."
    else:
        return f"GitHub API error ({resp.status_code}): {resp.text[:500]}"
