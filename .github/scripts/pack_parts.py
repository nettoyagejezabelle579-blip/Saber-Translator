"""Pack the built app into ordinary .zip parts, each under the release asset limit.

Every part contains paths under ``Saber-Translator/``; extracting all parts
into the same folder (Windows "Extract All" works) recreates the full app.
Files are ordered so the program and default models come first and the
optional models last; all parts are needed for a working install.

Usage: pack_parts.py DIST_DIR OUTPUT_PREFIX [LIMIT_BYTES]
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

# Model weights barely compress; storing them keeps packing fast.
STORED_SUFFIXES = {".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".bin", ".ttf", ".ttc", ".otf"}
OPTIONAL_MODEL_DIRS = ("paddleocr_vl_1_6", "ctd", "yolo")
OPTIONAL_MODEL_FILES = ("big-lama.safetensors",)


def _is_optional(relative: Path) -> bool:
    parts = relative.parts
    if "models" not in parts:
        return False
    after = parts[parts.index("models") + 1:]
    return bool(after) and (after[0] in OPTIONAL_MODEL_DIRS or relative.name in OPTIONAL_MODEL_FILES)


def plan_parts(files: list[tuple[Path, int]], limit: int) -> list[list[Path]]:
    """Greedy split by uncompressed size, so every zip is guaranteed under limit."""
    parts: list[list[Path]] = [[]]
    used = 0
    for path, size in files:
        if size > limit:
            raise SystemExit(f"{path} ({size} bytes) is larger than one release asset")
        if used + size > limit and parts[-1]:
            parts.append([])
            used = 0
        parts[-1].append(path)
        used += size
    return parts


def main() -> None:
    dist = Path(sys.argv[1]).resolve()
    prefix = sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 1_950_000_000
    root = dist / "Saber-Translator"
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: (_is_optional(path.relative_to(dist)), str(path).lower()),
    )
    sized = [(path, path.stat().st_size) for path in files]
    parts = plan_parts(sized, limit)
    for index, members in enumerate(parts, start=1):
        target = Path(f"{prefix}-part{index}.zip")
        with zipfile.ZipFile(target, "w", allowZip64=True) as archive:
            for path in members:
                method = zipfile.ZIP_STORED if path.suffix.lower() in STORED_SUFFIXES else zipfile.ZIP_DEFLATED
                archive.write(path, path.relative_to(dist).as_posix(), compress_type=method, compresslevel=6)
        print(f"{target.name}: {len(members)} files, {target.stat().st_size / 1e6:,.0f} MB")
        if target.stat().st_size > limit:
            raise SystemExit(f"{target} exceeds the asset limit")


if __name__ == "__main__":
    main()
