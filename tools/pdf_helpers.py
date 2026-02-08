"""PDF helper utilities — markdown-to-HTML conversion, page range parsing,
and standalone PDF action functions.

These are extracted from PdfTool to keep file sizes manageable.
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_page_ranges(pages_str: str, max_pages: int) -> list[int]:
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


def inline_markdown(text: str) -> str:
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


def markdown_to_html(text: str) -> str:
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
            title = inline_markdown(heading_match.group(2))
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
            item = inline_markdown(list_match.group(1))
            html_lines.append(f"<li>{item}</li>")
            continue

        # Numbered list: 1. item
        num_match = re.match(r'^\d+[.)]\s+(.+)$', stripped)
        if num_match:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            item = inline_markdown(num_match.group(1))
            html_lines.append(f"<li>{item}</li>")
            continue

        # Regular paragraph
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        para = inline_markdown(stripped)
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


def html_to_pdf(fitz: Any, content: str, output_path: str) -> str:
    """Convert HTML content to a PDF file."""
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
        text = re.sub(r"<[^>]+>", "", content)
        page.insert_text(fitz.Point(72, 72), text[:3000], fontsize=11)
        doc.save(str(out))
        doc.close()

    size_kb = out.stat().st_size / 1024
    return f"Created PDF from HTML at {out} ({size_kb:.1f} KB)"


def pdf_to_images(fitz: Any, input_path: str, output_path: str, pages: str) -> str:
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
    page_indices = parse_page_ranges(pages, doc.page_count)

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


def add_watermark(fitz: Any, input_path: str, output_path: str, watermark_text: str) -> str:
    """Add diagonal watermark text to every page of a PDF."""
    if not input_path:
        return "Error: input_path is required for add_watermark."
    if not output_path:
        return "Error: output_path is required for add_watermark."
    if not watermark_text:
        return "Error: watermark_text is required for add_watermark."

    src = Path(input_path).expanduser()
    if not src.exists():
        return f"Error: File not found: {src}"

    out = Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(src))

    for page in doc:
        rect = page.rect
        # Diagonal watermark: center of page, rotated 45 degrees
        center = fitz.Point(rect.width / 2, rect.height / 2)
        font_size = min(rect.width, rect.height) / 8
        page.insert_text(
            center,
            watermark_text,
            fontsize=font_size,
            fontname="helv",
            color=(0.75, 0.75, 0.75),
            rotate=45,
            overlay=True,
        )

    doc.save(str(out))
    num_pages = doc.page_count
    doc.close()
    return f"Added watermark '{watermark_text}' to {num_pages} page(s)\nSaved to {out}"
