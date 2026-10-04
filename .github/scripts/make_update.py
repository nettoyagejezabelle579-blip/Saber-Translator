"""Write the build manifest and an incremental update package.

Usage: make_update.py DIST_DIR BUILD_ID OUTPUT_PREFIX [PREVIOUS_MANIFEST] [LIMIT_BYTES]

* ``DIST_DIR/Saber-Translator/BUILD.json`` and ``build-manifest.json`` (sha256 of
  every file) are written into the app folder and next to the output.
* When the previous release's manifest is given, ``OUTPUT_PREFIX-update.zip``
  holds only files that are new or changed since that build, plus
  ``UPDATE-INFO.json`` (base build, new build, deleted files). The installer
  script applies it on top of the previous build and never touches ``data-v2``.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

STORED_SUFFIXES = {".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".bin", ".ttf", ".ttc", ".otf"}
# 每次建置內容都會變、但不影響程式的檔案不列入比對
VOLATILE = {"BUILD.json", "build-manifest.json"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in VOLATILE
    }


def main() -> None:
    dist = Path(sys.argv[1]).resolve()
    build_id = sys.argv[2]
    prefix = sys.argv[3]
    previous_path = Path(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else None
    limit = int(sys.argv[5]) if len(sys.argv) > 5 else 1_950_000_000
    root = dist / "Saber-Translator"

    files = build_manifest(root)
    build_info = {
        "build": build_id,
        "builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    manifest = {**build_info, "files": files}
    (root / "BUILD.json").write_text(json.dumps(build_info, indent=2), encoding="utf-8")
    for target in (root / "build-manifest.json", Path("build-manifest.json")):
        target.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    print(f"manifest: {len(files)} files, build {build_id}")

    if previous_path is None or not previous_path.is_file():
        print("no previous manifest; skipping incremental update")
        return
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    old_files = previous.get("files", {})
    changed = [name for name, digest in files.items() if old_files.get(name) != digest]
    deleted = sorted(name for name in old_files if name not in files)
    size = sum((root / name).stat().st_size for name in changed)
    print(f"update from {previous.get('build')}: {len(changed)} changed, "
          f"{len(deleted)} deleted, {size / 1e6:,.0f} MB")
    if size > limit:
        print("incremental update too large for one asset; full parts only")
        return
    info = {"base": previous.get("build"), "build": build_id, "deleted": deleted}
    Path("update-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    with zipfile.ZipFile(f"{prefix}-update.zip", "w", allowZip64=True) as archive:
        for name in changed + ["BUILD.json", "build-manifest.json"]:
            path = root / name
            method = zipfile.ZIP_STORED if path.suffix.lower() in STORED_SUFFIXES else zipfile.ZIP_DEFLATED
            archive.write(path, f"Saber-Translator/{name}", compress_type=method, compresslevel=6)
        archive.writestr("Saber-Translator/UPDATE-INFO.json", json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
