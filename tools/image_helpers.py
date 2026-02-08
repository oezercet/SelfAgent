"""Helper functions for image_tool — watermark, thumbnail, info, batch.

Extracted from ImageTool to keep individual files under 300 lines.
"""

import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def add_watermark(
    Image: Any,
    ImageDraw: Any,
    ImageFont: Any,
    src: Path,
    output_path: str,
    text: str,
    resolve_output: Callable[[Path, str, str], Path],
) -> str:
    """Add a semi-transparent watermark to an image.

    Parameters
    ----------
    Image, ImageDraw, ImageFont:
        PIL modules (passed to avoid top-level import).
    src:
        Source image path.
    output_path:
        Explicit output path string (may be empty).
    text:
        The watermark text.
    resolve_output:
        Callable(src, output_path, suffix) -> Path that builds the
        destination path (mirrors ImageTool._output_path).
    """
    if not text:
        return "Error: watermark_text is required."

    img = Image.open(src).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Use default font, sized to ~3% of image width
    font_size = max(16, img.width // 30)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Bottom-right corner with padding
    x = img.width - tw - 20
    y = img.height - th - 20

    # Semi-transparent white text
    draw.text((x, y), text, fill=(255, 255, 255, 128), font=font)
    result = Image.alpha_composite(img, overlay).convert("RGB")

    out = resolve_output(src, output_path, "_watermarked")
    result.save(out)
    return f"Added watermark '{text}'\nSaved to {out}"


def get_info(Image: Any, src: Path) -> str:
    """Return image metadata and details as a human-readable string."""
    img = Image.open(src)
    w, h = img.size
    file_size = src.stat().st_size
    info_lines = [
        f"File: {src.name}",
        f"Format: {img.format or src.suffix}",
        f"Mode: {img.mode}",
        f"Size: {w}x{h} pixels",
        f"File size: {file_size / 1024:.1f} KB",
    ]
    if hasattr(img, "n_frames") and img.n_frames > 1:
        info_lines.append(f"Frames: {img.n_frames}")
    if img.info.get("dpi"):
        info_lines.append(f"DPI: {img.info['dpi']}")
    img.close()
    return "\n".join(info_lines)


def create_thumbnail(
    Image: Any,
    src: Path,
    output_path: str,
    size: int,
    resolve_output: Callable[[Path, str, str], Path],
) -> str:
    """Create a square thumbnail with center crop.

    Parameters
    ----------
    Image:
        PIL Image module.
    src:
        Source image path.
    output_path:
        Explicit output path string (may be empty).
    size:
        Thumbnail size in pixels (longest side).
    resolve_output:
        Callable(src, output_path, suffix) -> Path.
    """
    size = max(16, min(1024, size))
    img = Image.open(src)
    w, h = img.size

    # Center crop to square
    short = min(w, h)
    left = (w - short) // 2
    top = (h - short) // 2
    img = img.crop((left, top, left + short, top + short))
    img = img.resize((size, size), Image.LANCZOS)

    out = resolve_output(src, output_path, f"_thumb_{size}")
    img.save(out)
    img.close()
    return f"Created {size}x{size} thumbnail\nSaved to {out}"


def batch_process(
    Image: Any,
    ImageDraw: Any,
    ImageFont: Any,
    input_paths: list,
    output_path: str,
    width: int,
    height: int,
    fmt: str,
    quality: int,
) -> str:
    """Apply the same operation to multiple images at once.

    Parameters
    ----------
    Image, ImageDraw, ImageFont:
        PIL modules.
    input_paths:
        List of source image path strings.
    output_path:
        Output directory path string.
    width, height:
        Target dimensions for resize (0 means skip).
    fmt:
        Target format string (empty means keep original).
    quality:
        JPEG compression quality (0 means skip).
    """
    if not input_paths:
        return "Error: input_paths is required for batch_process."
    if not output_path:
        return "Error: output_path (directory) is required for batch_process."

    out_dir = Path(output_path).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine what operations to apply
    operations: list[str] = []
    if width or height:
        operations.append("resize")
    if fmt:
        operations.append("convert")
    if quality:
        operations.append("compress")

    if not operations:
        return (
            "Error: Specify at least one operation "
            "(width/height for resize, format for convert, quality for compress)."
        )

    results: list[str] = []
    for path_str in input_paths:
        src = Path(path_str).expanduser()
        if not src.exists():
            results.append(f"SKIP {src.name}: file not found")
            continue

        try:
            img = Image.open(src)
            orig_w, orig_h = img.size

            # Resize
            if width or height:
                if width and height:
                    new_size = (width, height)
                elif width:
                    ratio = width / orig_w
                    new_size = (width, int(orig_h * ratio))
                else:
                    ratio = height / orig_h
                    new_size = (int(orig_w * ratio), height)
                img = img.resize(new_size, Image.LANCZOS)

            # Determine output format
            out_fmt = fmt.lower().strip(".") if fmt else src.suffix.lstrip(".")
            ext = f".{out_fmt}"

            # Convert mode for JPEG
            fmt_map = {
                "jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP",
                "bmp": "BMP", "gif": "GIF", "tiff": "TIFF",
            }
            pil_fmt = fmt_map.get(out_fmt, out_fmt.upper())
            if pil_fmt == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            out_file = out_dir / f"{src.stem}{ext}"
            save_kwargs: dict[str, Any] = {}
            if quality and pil_fmt == "JPEG":
                save_kwargs["quality"] = max(1, min(100, quality))
                save_kwargs["optimize"] = True

            img.save(out_file, format=pil_fmt, **save_kwargs)
            img.close()
            results.append(f"OK {src.name} -> {out_file.name}")
        except Exception as e:
            results.append(f"FAIL {src.name}: {e}")

    ops_str = ", ".join(operations)
    return f"Batch {ops_str} on {len(input_paths)} images:\n" + "\n".join(results)
