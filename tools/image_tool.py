"""Image tool — perform common image manipulation operations.

Uses Pillow (PIL) for resize, crop, format conversion,
compression, and watermarking.
"""

import logging
from pathlib import Path
from typing import Any

from tools.base import BaseTool
from tools.image_helpers import (
    add_watermark,
    batch_process,
    create_thumbnail,
    get_info,
)

logger = logging.getLogger(__name__)


class ImageTool(BaseTool):
    name = "image"
    description = (
        "Manipulate images: resize, crop, convert formats, compress, "
        "and add watermarks."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["resize", "crop", "convert", "compress", "add_watermark", "batch_process", "get_info", "create_thumbnail"],
                "description": "The image action to perform",
            },
            "input_path": {
                "type": "string",
                "description": "Path to the source image",
            },
            "output_path": {
                "type": "string",
                "description": "Path for the output image",
            },
            "width": {
                "type": "integer",
                "description": "Target width in pixels (for 'resize')",
            },
            "height": {
                "type": "integer",
                "description": "Target height in pixels (for 'resize')",
            },
            "x": {
                "type": "integer",
                "description": "Crop start X coordinate (for 'crop')",
            },
            "y": {
                "type": "integer",
                "description": "Crop start Y coordinate (for 'crop')",
            },
            "crop_width": {
                "type": "integer",
                "description": "Crop width (for 'crop')",
            },
            "crop_height": {
                "type": "integer",
                "description": "Crop height (for 'crop')",
            },
            "format": {
                "type": "string",
                "description": "Target format (for 'convert'), e.g. 'png', 'jpg', 'webp'",
            },
            "quality": {
                "type": "integer",
                "description": "Compression quality 1-100 (for 'compress')",
            },
            "watermark_text": {
                "type": "string",
                "description": "Watermark text (for 'add_watermark')",
            },
            "input_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of image paths (for 'batch_process')",
            },
            "size": {
                "type": "integer",
                "description": "Thumbnail size in pixels, longest side (for 'create_thumbnail', default 150)",
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return "Error: Pillow is not installed. Run: pip install Pillow"

        # batch_process and get_info handle their own path validation
        if action == "batch_process":
            try:
                return batch_process(
                    Image, ImageDraw, ImageFont,
                    kwargs.get("input_paths", []),
                    kwargs.get("output_path", ""),
                    kwargs.get("width", 0),
                    kwargs.get("height", 0),
                    kwargs.get("format", ""),
                    kwargs.get("quality", 0),
                )
            except Exception as e:
                logger.exception("Image tool error: %s", action)
                return f"Image error: {e}"

        input_path = kwargs.get("input_path", "")
        if not input_path:
            return "Error: input_path is required."

        src = Path(input_path).expanduser()
        if not src.exists():
            return f"Error: File not found: {src}"

        try:
            if action == "resize":
                return self._resize(
                    Image, src,
                    kwargs.get("output_path", ""),
                    kwargs.get("width", 0),
                    kwargs.get("height", 0),
                )
            elif action == "crop":
                return self._crop(
                    Image, src,
                    kwargs.get("output_path", ""),
                    kwargs.get("x", 0),
                    kwargs.get("y", 0),
                    kwargs.get("crop_width", 0),
                    kwargs.get("crop_height", 0),
                )
            elif action == "convert":
                return self._convert(
                    Image, src,
                    kwargs.get("output_path", ""),
                    kwargs.get("format", ""),
                )
            elif action == "compress":
                return self._compress(
                    Image, src,
                    kwargs.get("output_path", ""),
                    kwargs.get("quality", 75),
                )
            elif action == "add_watermark":
                return add_watermark(
                    Image, ImageDraw, ImageFont, src,
                    kwargs.get("output_path", ""),
                    kwargs.get("watermark_text", ""),
                    self._output_path,
                )
            elif action == "get_info":
                return get_info(Image, src)
            elif action == "create_thumbnail":
                return create_thumbnail(
                    Image, src,
                    kwargs.get("output_path", ""),
                    kwargs.get("size", 150),
                    self._output_path,
                )
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Image tool error: %s", action)
            return f"Image error: {e}"

    def _output_path(self, src: Path, output_path: str, suffix: str = "") -> Path:
        if output_path:
            out = Path(output_path).expanduser()
        else:
            out = src.with_stem(src.stem + (suffix or "_output"))
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def _resize(self, Image: Any, src: Path, output_path: str, width: int, height: int) -> str:
        img = Image.open(src)
        orig_w, orig_h = img.size

        if width and height:
            new_size = (width, height)
        elif width:
            ratio = width / orig_w
            new_size = (width, int(orig_h * ratio))
        elif height:
            ratio = height / orig_h
            new_size = (int(orig_w * ratio), height)
        else:
            return "Error: width and/or height required for resize."

        resized = img.resize(new_size, Image.LANCZOS)
        out = self._output_path(src, output_path, "_resized")
        resized.save(out)
        return f"Resized {orig_w}x{orig_h} -> {new_size[0]}x{new_size[1]}\nSaved to {out}"

    def _crop(self, Image: Any, src: Path, output_path: str,
              x: int, y: int, crop_width: int, crop_height: int) -> str:
        if not crop_width or not crop_height:
            return "Error: crop_width and crop_height are required for crop."

        img = Image.open(src)
        box = (x, y, x + crop_width, y + crop_height)
        cropped = img.crop(box)
        out = self._output_path(src, output_path, "_cropped")
        cropped.save(out)
        return f"Cropped region ({x},{y}) {crop_width}x{crop_height}\nSaved to {out}"

    def _convert(self, Image: Any, src: Path, output_path: str, fmt: str) -> str:
        if not fmt:
            return "Error: format is required for convert."

        fmt = fmt.lower().strip(".")
        fmt_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP",
                    "bmp": "BMP", "gif": "GIF", "tiff": "TIFF"}
        pil_fmt = fmt_map.get(fmt, fmt.upper())

        img = Image.open(src)
        if pil_fmt == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        if output_path:
            out = Path(output_path).expanduser()
        else:
            out = src.with_suffix(f".{fmt}")
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, format=pil_fmt)
        return f"Converted {src.suffix} -> .{fmt}\nSaved to {out}"

    def _compress(self, Image: Any, src: Path, output_path: str, quality: int) -> str:
        quality = max(1, min(100, quality))
        img = Image.open(src)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        out = self._output_path(src, output_path, "_compressed")
        if out.suffix.lower() not in (".jpg", ".jpeg"):
            out = out.with_suffix(".jpg")

        original_size = src.stat().st_size
        img.save(out, format="JPEG", quality=quality, optimize=True)
        new_size = out.stat().st_size
        reduction = (1 - new_size / original_size) * 100

        return (
            f"Compressed with quality={quality}\n"
            f"Original: {original_size / 1024:.1f} KB\n"
            f"Compressed: {new_size / 1024:.1f} KB ({reduction:.1f}% reduction)\n"
            f"Saved to {out}"
        )
