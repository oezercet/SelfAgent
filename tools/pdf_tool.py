"""PDF tool — create, read, merge, split, and convert PDFs.

Uses PyMuPDF (fitz) for reading/splitting/merging.
Creates PDFs from text/markdown/HTML using Story API for rich formatting.
"""

import logging
import re
from pathlib import Path
from typing import Any

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class PdfTool(BaseTool):
    name = "pdf"
    description = (
        "Work with PDFs: create from text, read content, merge files, "
        "split pages, and convert HTML to PDF."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "create_pdf",
                    "read_pdf",
                    "merge_pdfs",
                    "split_pdf",
                    "html_to_pdf",
                    "pdf_to_images",
                ],
                "description": "The PDF action to perform",
            },
            "input_path": {
                "type": "string",
                "description": "Path to the input PDF file",
            },
            "output_path": {
                "type": "string",
                "description": "Path for the output PDF file",
            },
            "content": {
                "type": "string",
                "description": "Text or HTML content (for 'create_pdf', 'html_to_pdf')",
            },
            "input_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of PDF file paths (for 'merge_pdfs')",
            },
            "pages": {
                "type": "string",
                "description": "Page range, e.g. '1-3,5,8-10' (for 'split_pdf', 'read_pdf')",
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            import fitz  # PyMuPDF
        except ImportError:
            return "Error: PyMuPDF is not installed. Run: pip install PyMuPDF"

        try:
            if action == "create_pdf":
                return self._create_pdf(
                    fitz,
                    kwargs.get("content", ""),
                    kwargs.get("output_path", ""),
                )
            elif action == "read_pdf":
                return self._read_pdf(
                    fitz,
                    kwargs.get("input_path", ""),
                    kwargs.get("pages", ""),
                )
            elif action == "merge_pdfs":
                return self._merge_pdfs(
                    fitz,
                    kwargs.get("input_paths", []),
                    kwargs.get("output_path", ""),
                )
            elif action == "split_pdf":
                return self._split_pdf(
                    fitz,
                    kwargs.get("input_path", ""),
                    kwargs.get("output_path", ""),
                    kwargs.get("pages", ""),
                )
            elif action == "html_to_pdf":
                return self._html_to_pdf(
                    fitz,
                    kwargs.get("content", ""),
                    kwargs.get("output_path", ""),
                )
            elif action == "pdf_to_images":
                return self._pdf_to_images(
                    fitz,
                    kwargs.get("input_path", ""),
                    kwargs.get("output_path", ""),
                    kwargs.get("pages", ""),
                )
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("PDF error: %s", action)
            return f"PDF error: {e}"

    def _parse_page_ranges(self, pages_str: str, max_pages: int) -> list[int]:
        """Parse '1-3,5,8-10' into a list of 0-based page indices."""
        if not pages_str:
            return list(range(max_pages))

        result = []
        for part in pages_str.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                start = max(1, int(start.strip()))
                end = min(max_pages, int(end.strip()))
                result.extend(range(start - 1, end))
            else:
                page = int(part.strip()) - 1
                if 0 <= page < max_pages:
                    result.append(page)
        return sorted(set(result))

    def _markdown_to_html(self, text: str) -> str:
        """Convert markdown-style content to styled HTML for PDF rendering."""
        lines = text.split("\n")
        html_lines = []
        in_list = False

        for line in lines:
            stripped = line.strip()

            # Blank line
            if not stripped:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append("<br/>")
                continue

            # Headings: # ## ### ####
            heading_match = re.match(r'^(#{1,4})\s+(.+)$', stripped)
            if heading_match:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                level = len(heading_match.group(1))
                title = self._inline_markdown(heading_match.group(2))
                html_lines.append(f"<h{level}>{title}</h{level}>")
                continue

            # Horizontal rule: --- or ***
            if re.match(r'^[-*_]{3,}\s*$', stripped):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append("<hr/>")
                continue

            # Unordered list: - item or * item
            list_match = re.match(r'^[-*]\s+(.+)$', stripped)
            if list_match:
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                item = self._inline_markdown(list_match.group(1))
                html_lines.append(f"<li>{item}</li>")
                continue

            # Numbered list: 1. item
            num_match = re.match(r'^\d+[.)]\s+(.+)$', stripped)
            if num_match:
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                item = self._inline_markdown(num_match.group(1))
                html_lines.append(f"<li>{item}</li>")
                continue

            # Regular paragraph
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            para = self._inline_markdown(stripped)
            html_lines.append(f"<p>{para}</p>")

        if in_list:
            html_lines.append("</ul>")

        body = "\n".join(html_lines)

        # Wrap in full HTML with CSS styling
        return f"""<!DOCTYPE html>
<html>
<head>
<style>
body {{
    font-family: sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
}}
h1 {{
    font-size: 20pt;
    color: #2c3e50;
    border-bottom: 2px solid #3498db;
    padding-bottom: 6px;
    margin-top: 16px;
    margin-bottom: 10px;
}}
h2 {{
    font-size: 16pt;
    color: #2c3e50;
    border-bottom: 1px solid #bdc3c7;
    padding-bottom: 4px;
    margin-top: 14px;
    margin-bottom: 8px;
}}
h3 {{
    font-size: 13pt;
    color: #34495e;
    margin-top: 12px;
    margin-bottom: 6px;
}}
h4 {{
    font-size: 11pt;
    color: #34495e;
    margin-top: 10px;
    margin-bottom: 4px;
}}
p {{
    margin: 4px 0;
}}
ul {{
    margin: 4px 0;
    padding-left: 24px;
}}
li {{
    margin: 3px 0;
}}
hr {{
    border: none;
    border-top: 1px solid #bdc3c7;
    margin: 12px 0;
}}
strong {{
    font-weight: bold;
}}
em {{
    font-style: italic;
}}
code {{
    font-family: monospace;
    background: #ecf0f1;
    padding: 1px 4px;
    font-size: 10pt;
}}
</style>
</head>
<body>
{body}
</body>
</html>"""

    def _inline_markdown(self, text: str) -> str:
        """Convert inline markdown (bold, italic, code) to HTML."""
        # Escape HTML entities
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Bold: **text** or __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        # Italic: *text* or _text_
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<em>\1</em>', text)
        # Inline code: `text`
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        return text

    def _create_pdf(self, fitz: Any, content: str, output_path: str) -> str:
        if not content:
            return "Error: content is required for create_pdf."
        if not output_path:
            return "Error: output_path is required for create_pdf."

        out = Path(output_path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)

        # Convert markdown content to styled HTML
        html = self._markdown_to_html(content)

        # Use Story API for professional rendering with auto-pagination
        try:
            story = fitz.Story(html=html)
            writer = fitz.DocumentWriter(str(out))
            mediabox = fitz.paper_rect("A4")
            margin = 60
            content_rect = mediabox + fitz.Rect(margin, margin, -margin, -margin)

            num_pages = 0
            more = True
            while more:
                dev = writer.begin_page(mediabox)
                more, _ = story.place(content_rect)
                story.draw(dev)
                writer.end_page()
                num_pages += 1
                if num_pages >= 50:
                    break

            writer.close()
            size_kb = out.stat().st_size / 1024
            return f"Created PDF with {num_pages} page(s) at {out} ({size_kb:.0f} KB)"
        except Exception as e:
            logger.warning("Story API failed, falling back to plain text: %s", e)
            # Fallback to plain insert_textbox
            doc = fitz.open()
            page = doc.new_page()
            rect = fitz.Rect(60, 60, page.rect.width - 60, page.rect.height - 60)
            # Strip markdown for fallback
            plain = re.sub(r'[#*_`]', '', content)
            page.insert_textbox(rect, plain, fontsize=11, fontname="helv")
            doc.save(str(out))
            num_pages = doc.page_count
            doc.close()
            return f"Created PDF with {num_pages} page(s) at {out}"

    def _read_pdf(self, fitz: Any, input_path: str, pages: str) -> str:
        if not input_path:
            return "Error: input_path is required for read_pdf."

        src = Path(input_path).expanduser()
        if not src.exists():
            return f"Error: File not found: {src}"

        doc = fitz.open(str(src))
        page_indices = self._parse_page_ranges(pages, doc.page_count)

        text_parts = []
        for idx in page_indices:
            page = doc[idx]
            text = page.get_text()
            text_parts.append(f"--- Page {idx + 1} ---\n{text}")

        num_pages = doc.page_count
        doc.close()

        full_text = "\n\n".join(text_parts)
        if len(full_text) > 20000:
            full_text = full_text[:20000] + "\n\n... [truncated]"

        return f"PDF: {src.name} ({num_pages} pages)\n\n{full_text}"

    def _merge_pdfs(self, fitz: Any, input_paths: list, output_path: str) -> str:
        if not input_paths or len(input_paths) < 2:
            return "Error: At least 2 input_paths are required for merge_pdfs."
        if not output_path:
            return "Error: output_path is required for merge_pdfs."

        out = Path(output_path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)

        merged = fitz.open()
        total_pages = 0

        for path_str in input_paths:
            src = Path(path_str).expanduser()
            if not src.exists():
                return f"Error: File not found: {src}"
            doc = fitz.open(str(src))
            merged.insert_pdf(doc)
            total_pages += doc.page_count
            doc.close()

        merged.save(str(out))
        merged.close()
        return f"Merged {len(input_paths)} PDFs ({total_pages} pages) into {out}"

    def _split_pdf(self, fitz: Any, input_path: str, output_path: str, pages: str) -> str:
        if not input_path:
            return "Error: input_path is required for split_pdf."
        if not output_path:
            return "Error: output_path is required for split_pdf."
        if not pages:
            return "Error: pages is required for split_pdf (e.g. '1-3,5')."

        src = Path(input_path).expanduser()
        if not src.exists():
            return f"Error: File not found: {src}"

        out = Path(output_path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(str(src))
        page_indices = self._parse_page_ranges(pages, doc.page_count)

        new_doc = fitz.open()
        for idx in page_indices:
            new_doc.insert_pdf(doc, from_page=idx, to_page=idx)

        new_doc.save(str(out))
        total = new_doc.page_count
        new_doc.close()
        doc.close()

        return f"Extracted {total} page(s) from {src.name} to {out}"

    def _html_to_pdf(self, fitz: Any, content: str, output_path: str) -> str:
        if not content:
            return "Error: content (HTML) is required for html_to_pdf."
        if not output_path:
            return "Error: output_path is required for html_to_pdf."

        out = Path(output_path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)

        # Use fitz Story API for HTML rendering
        try:
            story = fitz.Story(html=content)
            writer = fitz.DocumentWriter(str(out))
            mediabox = fitz.paper_rect("letter")
            where = mediabox + fitz.Rect(72, 72, -72, -72)  # margins

            more = True
            while more:
                dev = writer.begin_page(mediabox)
                more, _ = story.place(where)
                story.draw(dev)
                writer.end_page()

            writer.close()
        except AttributeError:
            # Fallback: treat HTML as plain text
            doc = fitz.open()
            page = doc.new_page()
            # Strip basic HTML tags for fallback
            import re
            text = re.sub(r"<[^>]+>", "", content)
            page.insert_text(fitz.Point(72, 72), text[:3000], fontsize=11)
            doc.save(str(out))
            doc.close()

        size_kb = out.stat().st_size / 1024
        return f"Created PDF from HTML at {out} ({size_kb:.1f} KB)"

    def _pdf_to_images(self, fitz: Any, input_path: str, output_path: str, pages: str) -> str:
        """Convert PDF pages to PNG images."""
        if not input_path:
            return "Error: input_path is required for pdf_to_images."
        if not output_path:
            return "Error: output_path is required for pdf_to_images (directory path)."

        src = Path(input_path).expanduser()
        if not src.exists():
            return f"Error: File not found: {src}"

        out_dir = Path(output_path).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(str(src))
        page_indices = self._parse_page_ranges(pages, doc.page_count)

        saved = []
        for idx in page_indices:
            page = doc[idx]
            # 2x zoom for good quality (144 DPI)
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            img_path = out_dir / f"{src.stem}_page_{idx + 1}.png"
            pix.save(str(img_path))
            saved.append(str(img_path))

        doc.close()
        return f"Converted {len(saved)} page(s) to images in {out_dir}:\n" + "\n".join(saved)
