"""回報的閃退：更新後留下缺少 METADATA 的舊 aiohttp-*.dist-info，openai 匯入時比較版本得到 None。"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run(tmp_path: Path, *, with_fix: bool) -> subprocess.CompletedProcess[str]:
    stale = tmp_path / "site" / "aiohttp-3.0.0.dist-info" / "licenses"
    stale.mkdir(parents=True)
    (stale / "LICENSE.txt").write_text("leftover from an older build", encoding="utf-8")
    script = textwrap.dedent(
        f"""\
        import sys
        sys.path.insert(0, {str(tmp_path / "site")!r})
        sys.path.insert(0, {str(PROJECT_ROOT)!r})
        import importlib.metadata as md
        print("raw", md.version("aiohttp"))
        if {with_fix!r}:
            from src.backend_v2.metadata_compat import install
            install()
        print("fixed", md.version("aiohttp"))
        import openai._vendor.httpx_aiohttp.transport  # 這裡以前會 TypeError
        print("openai ok")
        """
    )
    return subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, encoding="utf-8", timeout=180
    )


def test_leftover_dist_info_without_metadata_no_longer_crashes(tmp_path) -> None:
    import pytest

    pytest.importorskip("openai._vendor.httpx_aiohttp.transport")
    broken = _run(tmp_path / "without", with_fix=False)
    assert "raw None" in broken.stdout  # 重現：Python 先讀到舊資料夾
    assert "'>=' not supported" in broken.stderr

    fixed = _run(tmp_path / "with", with_fix=True)
    assert fixed.returncode == 0, fixed.stderr
    import aiohttp

    assert f"fixed {aiohttp.__version__}" in fixed.stdout
    assert "openai ok" in fixed.stdout


def test_fallback_keeps_normal_answers_and_missing_packages() -> None:
    import importlib.metadata as md

    from src.backend_v2.metadata_compat import install

    install()
    install()  # 重複安裝不會包兩層
    assert md.version("pytest")
    import pytest

    with pytest.raises(md.PackageNotFoundError):
        md.version("definitely-not-installed-saber-package")
