"""Chapter (volume) covers for the bookshelf.

Covers live as small JPEG files in ``<data root>/chapter-covers`` instead of
the database, so the strictly versioned storage schema stays unchanged and
existing libraries need no conversion. A chapter without its own cover shows
a thumbnail of its first page (cached next to the custom covers).
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

COVER_DIR = "chapter-covers"
AUTO_DIR = "auto"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
COVER_SIZE = (600, 900)  # 長邊上限，接近日本單行本比例
THUMB_SIZE = (360, 540)
_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _check_id(value: str) -> str:
    if not _SAFE_ID.fullmatch(value or ""):
        raise ValueError("invalid id")
    return value


def cover_root(data_root: Path) -> Path:
    return Path(data_root) / COVER_DIR


def custom_cover_path(data_root: Path, chapter_id: str) -> Path:
    return cover_root(data_root) / f"{_check_id(chapter_id)}.jpg"


def auto_cover_path(data_root: Path, chapter_id: str, asset_id: str) -> Path:
    return cover_root(data_root) / AUTO_DIR / f"{_check_id(chapter_id)}-{_check_id(asset_id)}.jpg"


def _to_jpeg(image: Image.Image, size: tuple[int, int]) -> bytes:
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.split()[-1])
        image = background
    else:
        image = image.convert("RGB")
    image.thumbnail(size, Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88, optimize=True)
    return buffer.getvalue()


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def save_custom_cover(data_root: Path, chapter_id: str, stream: BinaryIO) -> Path:
    raw = stream.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("cover image is larger than 20 MB")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            data = _to_jpeg(image, COVER_SIZE)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("cover must be an image file") from exc
    path = custom_cover_path(data_root, chapter_id)
    _write_atomic(path, data)
    return path


def remove_covers(data_root: Path, chapter_id: str) -> None:
    custom_cover_path(data_root, chapter_id).unlink(missing_ok=True)
    auto_dir = cover_root(data_root) / AUTO_DIR
    if auto_dir.is_dir():
        for stale in auto_dir.glob(f"{_check_id(chapter_id)}-*.jpg"):
            stale.unlink(missing_ok=True)


def auto_cover(data_root: Path, chapter_id: str, asset_id: str, source: Path) -> Path:
    """Thumbnail of the chapter's first page, rebuilt when the first page changes."""
    path = auto_cover_path(data_root, chapter_id, asset_id)
    if path.is_file():
        return path
    auto_dir = path.parent
    if auto_dir.is_dir():
        for stale in auto_dir.glob(f"{chapter_id}-*.jpg"):
            stale.unlink(missing_ok=True)
    with Image.open(source) as image:
        image.load()
        _write_atomic(path, _to_jpeg(image, THUMB_SIZE))
    return path
