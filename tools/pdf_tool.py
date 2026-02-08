"""PDF tool — create, read, merge, split, and convert PDFs.

Uses PyMuPDF (fitz) for reading/splitting/merging.
Creates PDFs from text/markdown/HTML using Story API for rich formatting.
"""

import logging
import re
from pathlib import Path
from typing import Any

from tools.base import BaseTool
from tools.pdf_helpers import (
    add_watermark,
    html_to_pdf,
    markdown_to_html,
    parse_page_ranges,
    pdf_to_images,
)

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
                    "add_watermark",
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
            "watermark_text": {
                "type": "string",
                "description": "Watermark text (for 'add_watermark')",
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
                return html_to_pdf(
                    fitz,
                    kwargs.get("content", ""),
                    kwargs.get("output_path", ""),
                )
            elif action == "pdf_to_images":
                return pdf_to_images(
                    fitz,
                    kwargs.get("input_path", ""),
                    kwargs.get("output_path", ""),
                    kwargs.get("pages", ""),
                )
            elif action == "add_watermark":
                return add_watermark(
                    fitz,
                    kwargs.get("input_path", ""),
                    kwargs.get("output_path", ""),
                    kwargs.get("watermark_text", ""),
                )
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("PDF error: %s", action)
            return f"PDF error: {e}"

    def _create_pdf(self, fitz: Any, content: str, output_path: str) -> str:
        if not content:
            return "Error: content is required for create_pdf."
        if not output_path:
            return "Error: output_path is required for create_pdf."

        out = Path(output_path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)

        # Convert markdown content to styled HTML
        html = markdown_to_html(content)

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
        page_indices = parse_page_ranges(pages, doc.page_count)

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
        page_indices = parse_page_ranges(pages, doc.page_count)

        new_doc = fitz.open()
        for idx in page_indices:
            new_doc.insert_pdf(doc, from_page=idx, to_page=idx)

        new_doc.save(str(out))
        total = new_doc.page_count
        new_doc.close()
        doc.close()

        return f"Extracted {total} page(s) from {src.name} to {out}"
