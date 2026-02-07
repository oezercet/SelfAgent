"""Image tool — perform common image manipulation operations.

Uses Pillow (PIL) for resize, crop, format conversion,
compression, and watermarking.
"""

import logging
from pathlib import Path
from typing import Any

from tools.base import BaseTool

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
                "enum": ["resize", "crop", "convert", "compress", "add_watermark", "batch_process", "get_info"],
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
                return self._batch_process(
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
                return self._add_watermark(
                    Image, ImageDraw, ImageFont, src,
                    kwargs.get("output_path", ""),
                    kwargs.get("watermark_text", ""),
                )
            elif action == "get_info":
                return self._get_info(Image, src)
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

    def _add_watermark(self, Image: Any, ImageDraw: Any, ImageFont: Any,
                       src: Path, output_path: str, text: str) -> str:
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

        out = self._output_path(src, output_path, "_watermarked")
        result.save(out)
        return f"Added watermark '{text}'\nSaved to {out}"

    def _get_info(self, Image: Any, src: Path) -> str:
        """Get image metadata and details."""
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

    def _batch_process(self, Image: Any, ImageDraw: Any, ImageFont: Any,
                       input_paths: list, output_path: str,
                       width: int, height: int, fmt: str, quality: int) -> str:
        """Apply the same operation to multiple images at once."""
        if not input_paths:
            return "Error: input_paths is required for batch_process."
        if not output_path:
            return "Error: output_path (directory) is required for batch_process."

        out_dir = Path(output_path).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)

        # Determine what operations to apply
        operations = []
        if width or height:
            operations.append("resize")
        if fmt:
            operations.append("convert")
        if quality:
            operations.append("compress")

        if not operations:
            return "Error: Specify at least one operation (width/height for resize, format for convert, quality for compress)."

        results = []
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
                fmt_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP",
                           "bmp": "BMP", "gif": "GIF", "tiff": "TIFF"}
                pil_fmt = fmt_map.get(out_fmt, out_fmt.upper())
                if pil_fmt == "JPEG" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                out_file = out_dir / f"{src.stem}{ext}"
                save_kwargs = {}
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
