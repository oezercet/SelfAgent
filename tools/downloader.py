"""Downloader tool — download files, videos, and audio from the web.

Uses httpx for file downloads and yt-dlp for video/audio extraction.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from tools.base import BaseTool

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = Path.home() / "Downloads"


class DownloaderTool(BaseTool):
    name = "downloader"
    description = (
        "Download content: fetch files from URLs, download video or audio "
        "from streaming sites, and perform batch downloads."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "download_file",
                    "download_video",
                    "download_audio",
                    "batch_download",
                    "download_page",
                ],
                "description": "The download action to perform",
            },
            "url": {
                "type": "string",
                "description": "URL to download from (for single downloads)",
            },
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of URLs (for 'batch_download')",
            },
            "output_path": {
                "type": "string",
                "description": "Directory or file path for the downloaded content",
            },
            "format": {
                "type": "string",
                "description": "Desired format (for 'download_video', 'download_audio'), e.g. 'mp4', 'mp3'",
            },
            "quality": {
                "type": "string",
                "description": "Quality setting (for 'download_video'), e.g. 'best', '720p', '1080p'",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=120.0,
            follow_redirects=True,
            headers={"User-Agent": "SelfAgent-Downloader/1.0"},
        )

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            if action == "download_file":
                return await self._download_file(
                    kwargs.get("url", ""),
                    kwargs.get("output_path", ""),
                )
            elif action == "download_video":
                return await self._download_media(
                    kwargs.get("url", ""),
                    kwargs.get("output_path", ""),
                    kwargs.get("format", "mp4"),
                    kwargs.get("quality", "best"),
                    video=True,
                )
            elif action == "download_audio":
                return await self._download_media(
                    kwargs.get("url", ""),
                    kwargs.get("output_path", ""),
                    kwargs.get("format", "mp3"),
                    kwargs.get("quality", "best"),
                    video=False,
                )
            elif action == "batch_download":
                return await self._batch_download(
                    kwargs.get("urls", []),
                    kwargs.get("output_path", ""),
                )
            elif action == "download_page":
                return await self._download_page(
                    kwargs.get("url", ""),
                    kwargs.get("output_path", ""),
                )
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Download error: %s", action)
            return f"Download error: {e}"

    async def _download_file(self, url: str, output_path: str) -> str:
        if not url:
            return "Error: url is required."

        # Determine output path
        if output_path:
            out = Path(output_path).expanduser()
            if out.is_dir() or not out.suffix:
                out.mkdir(parents=True, exist_ok=True)
                filename = self._filename_from_url(url)
                out = out / filename
        else:
            DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
            filename = self._filename_from_url(url)
            out = DOWNLOAD_DIR / filename

        out.parent.mkdir(parents=True, exist_ok=True)

        # Stream download
        downloaded = 0
        async with self._client.stream("GET", url) as resp:
            resp.raise_for_status()
            content_length = resp.headers.get("content-length")
            total = int(content_length) if content_length else None

            with open(out, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)

        size_str = self._format_size(downloaded)
        return f"Downloaded {url}\nSaved to {out} ({size_str})"

    async def _download_media(self, url: str, output_path: str,
                              fmt: str, quality: str, video: bool) -> str:
        if not url:
            return "Error: url is required."

        out_dir = Path(output_path).expanduser() if output_path else DOWNLOAD_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        # Build yt-dlp command
        cmd = ["yt-dlp", "--no-warnings"]

        if video:
            if quality == "720p":
                cmd.extend(["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]"])
            elif quality == "1080p":
                cmd.extend(["-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]"])
            else:
                cmd.extend(["-f", "bestvideo+bestaudio/best"])

            if fmt:
                cmd.extend(["--merge-output-format", fmt])
        else:
            cmd.extend(["-x", "--audio-format", fmt or "mp3"])

        cmd.extend(["-o", str(out_dir / "%(title)s.%(ext)s"), url])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        except FileNotFoundError:
            return "Error: yt-dlp is not installed. Run: pip install yt-dlp"
        except asyncio.TimeoutError:
            return "Download timed out (5 min limit)."

        output = stdout.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")
            return f"yt-dlp error:\n{err[:2000]}"

        # Extract filename from output
        media_type = "Video" if video else "Audio"
        return f"{media_type} download complete.\nSaved to {out_dir}\n\n{output[-500:]}"

    async def _batch_download(self, urls: list, output_path: str) -> str:
        if not urls:
            return "Error: urls list is required."

        out_dir = Path(output_path).expanduser() if output_path else DOWNLOAD_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for i, url in enumerate(urls, 1):
            try:
                filename = self._filename_from_url(url)
                out = out_dir / filename
                downloaded = 0

                async with self._client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    with open(out, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
                            downloaded += len(chunk)

                results.append(f"  [{i}] OK: {filename} ({self._format_size(downloaded)})")
            except Exception as e:
                results.append(f"  [{i}] FAIL: {url} — {e}")

        return f"Batch download to {out_dir}:\n" + "\n".join(results)

    async def _download_page(self, url: str, output_path: str) -> str:
        """Download a complete web page as a single HTML file."""
        if not url:
            return "Error: url is required."

        resp = await self._client.get(url)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        html = resp.text

        # Determine output file
        if output_path:
            out = Path(output_path).expanduser()
            if out.is_dir() or not out.suffix:
                out.mkdir(parents=True, exist_ok=True)
                slug = urlparse(url).netloc.replace(".", "_")
                out = out / f"{slug}.html"
        else:
            DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
            slug = urlparse(url).netloc.replace(".", "_")
            out = DOWNLOAD_DIR / f"{slug}.html"

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")

        size_str = self._format_size(len(html.encode("utf-8")))
        return f"Page saved: {url}\nFile: {out} ({size_str})"

    def _filename_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        name = Path(parsed.path).name
        if not name or name == "/":
            name = "download"
        return name

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.2f} GB"
