"""Startup update check for the portable Windows build.

When Saber-Translator.exe starts, compare BUILD.json next to the exe with the
GitHub release the package is published to. If the release is newer, start
Update-Saber.ps1 in its own console window and tell the caller to exit: the
updater waits for this process to end, applies the update (data-v2 is never
touched) and starts Saber again with the check skipped.

Turn it off by creating ``data-v2/auto-update-off.txt``.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("saber.desktop.update")

OWNER = "nettoyagejezabelle579-blip"
REPO = "Saber-Translator"
TAG = "galaxy-zh-hant-cpu"
UPDATER_SCRIPT = "Update-Saber.ps1"
SKIP_ENV = "SABER_SKIP_UPDATE_CHECK"
DISABLE_FILE = "auto-update-off.txt"
SKIPPED_BUILD_FILE = "update-skipped.txt"
TOKEN_FILE = "github-token.txt"
TIMEOUT_SECONDS = 4.0


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return ""


def local_build(app_dir: Path) -> str:
    try:
        data = json.loads((app_dir / "BUILD.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return ""
    return str(data.get("build") or "") if isinstance(data, dict) else ""


def remote_build(release: dict[str, Any]) -> str:
    # 發布名稱的最後一段就是建置編號，例如「繁中免安裝版 (CPU) c94ce8d」
    words = str(release.get("name") or "").split()
    return words[-1] if words else ""


def fetch_release(token: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/releases/tags/{TAG}",
        headers={"User-Agent": "Saber-Updater", "Accept": "application/vnd.github+json"},
    )
    if token:
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def launch_updater(app_dir: Path) -> bool:
    script = app_dir / UPDATER_SCRIPT
    if "[switch]$Auto" not in _read_text(script):
        return False
    subprocess.Popen(
        [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(script), "-Auto", "-WaitPid", str(os.getpid()),
        ],
        cwd=str(app_dir),
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        close_fds=True,
    )
    return True


def check_and_launch(
    app_dir: Path,
    *,
    fetch: Callable[[str, float], dict[str, Any]] = fetch_release,
    launch: Callable[[Path], bool] = launch_updater,
    timeout: float = TIMEOUT_SECONDS,
) -> bool:
    """Return True when the updater was started and the app should exit."""
    data_dir = app_dir / "data-v2"
    if (data_dir / DISABLE_FILE).exists() or not (app_dir / UPDATER_SCRIPT).is_file():
        return False
    token = _read_text(data_dir / TOKEN_FILE)
    result: dict[str, Any] = {}

    def worker() -> None:
        try:
            result["release"] = fetch(token, timeout)
        except Exception as error:  # 沒網路、權杖失效、發布正在重建：照常開啟程式
            result["error"] = error

    # 整體最多等 timeout 秒，不讓網路問題拖慢開啟程式
    thread = threading.Thread(target=worker, name="saber-update-check", daemon=True)
    thread.start()
    thread.join(timeout)
    release = result.get("release")
    if not isinstance(release, dict):
        LOGGER.info("略過自動更新檢查：%s", result.get("error", "逾時"))
        return False
    remote = remote_build(release)
    local = local_build(app_dir)
    if not remote or remote == local or remote == _read_text(data_dir / SKIPPED_BUILD_FILE):
        return False
    names = [str(asset.get("name") or "") for asset in release.get("assets") or [] if isinstance(asset, dict)]
    if not any(name.endswith(".zip") for name in names):
        return False
    LOGGER.info("發現新版本 %s（目前 %s），啟動自動更新", remote, local or "未知")
    try:
        return launch(app_dir)
    except OSError as error:
        LOGGER.warning("無法啟動更新程式：%s", error)
        return False


def start_update_if_available() -> bool:
    """Entry point for the desktop role of the packaged Windows build."""
    if os.environ.pop(SKIP_ENV, None):
        return False
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    return check_and_launch(Path(sys.executable).resolve().parent)
