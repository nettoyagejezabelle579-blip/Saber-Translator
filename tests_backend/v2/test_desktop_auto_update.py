"""開啟 Saber-Translator.exe 時的自動更新檢查。"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.backend_v2.desktop import auto_update

RELEASE = {
    "name": "繁中免安裝版 (CPU) new1234",
    "assets": [{"name": "Saber-Translator-zhHant-CPU-update.zip"}, {"name": "update-info.json"}],
}


@pytest.fixture
def app_dir(tmp_path: Path) -> Path:
    (tmp_path / "data-v2").mkdir()
    (tmp_path / "BUILD.json").write_text(json.dumps({"build": "old1234"}), encoding="utf-8")
    (tmp_path / "Update-Saber.ps1").write_text("param([switch]$Auto)", encoding="utf-8")
    return tmp_path


def _run(app_dir: Path, release=RELEASE, **kwargs):
    launched: list[Path] = []
    tokens: list[str] = []

    def fetch(token: str, timeout: float):
        tokens.append(token)
        if isinstance(release, Exception):
            raise release
        return release

    def launch(path: Path) -> bool:
        launched.append(path)
        return True

    started = auto_update.check_and_launch(app_dir, fetch=fetch, launch=launch, **kwargs)
    return started, launched, tokens


def test_newer_release_starts_the_updater(app_dir):
    (app_dir / "data-v2" / "github-token.txt").write_text("secret\n", encoding="utf-8")
    started, launched, tokens = _run(app_dir)
    assert started is True
    assert launched == [app_dir]
    assert tokens == ["secret"]


def test_same_build_opens_normally(app_dir):
    (app_dir / "BUILD.json").write_text(json.dumps({"build": "new1234"}), encoding="utf-8")
    assert _run(app_dir)[:2] == (False, [])


def test_install_without_build_info_is_updated(app_dir):
    (app_dir / "BUILD.json").unlink()
    assert _run(app_dir)[0] is True


@pytest.mark.parametrize("error", [OSError("offline"), ValueError("bad json")])
def test_network_problems_never_block_startup(app_dir, error):
    assert _run(app_dir, release=error)[:2] == (False, [])


def test_slow_network_gives_up_quickly(app_dir):
    def slow_fetch(token, timeout):
        time.sleep(2)
        return RELEASE

    begin = time.monotonic()
    started = auto_update.check_and_launch(
        app_dir, fetch=slow_fetch, launch=lambda path: True, timeout=0.2,
    )
    assert started is False
    assert time.monotonic() - begin < 1.5


def test_can_be_turned_off(app_dir):
    (app_dir / "data-v2" / "auto-update-off.txt").write_text("", encoding="utf-8")
    assert _run(app_dir)[:2] == (False, [])


def test_declined_full_download_is_not_asked_again(app_dir):
    (app_dir / "data-v2" / "update-skipped.txt").write_text("new1234\r\n", encoding="utf-8")
    assert _run(app_dir)[0] is False
    newer = dict(RELEASE, name="繁中免安裝版 (CPU) next999")
    assert _run(app_dir, release=newer)[0] is True


def test_release_being_rebuilt_is_ignored(app_dir):
    assert _run(app_dir, release={"name": RELEASE["name"], "assets": []})[0] is False


def test_missing_updater_script_opens_normally(app_dir):
    (app_dir / "Update-Saber.ps1").unlink()
    assert _run(app_dir)[:2] == (False, [])


def test_old_updater_without_auto_mode_is_not_launched(app_dir, monkeypatch):
    (app_dir / "Update-Saber.ps1").write_text("param([switch]$Offline)", encoding="utf-8")
    popen_calls = []
    monkeypatch.setattr(auto_update.subprocess, "Popen", lambda *a, **k: popen_calls.append(a))
    assert auto_update.launch_updater(app_dir) is False
    assert popen_calls == []


def test_launch_passes_auto_mode_and_pid(app_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(auto_update.subprocess, "Popen", lambda args, **kwargs: calls.append(args))
    assert auto_update.launch_updater(app_dir) is True
    args = calls[0]
    assert args[0] == "powershell.exe"
    assert str(app_dir / "Update-Saber.ps1") in args
    assert "-Auto" in args and "-WaitPid" in args


def test_relaunch_after_update_skips_the_check(monkeypatch):
    monkeypatch.setenv(auto_update.SKIP_ENV, "1")
    monkeypatch.setattr(auto_update, "check_and_launch", lambda *a, **k: pytest.fail("should not check"))
    assert auto_update.start_update_if_available() is False
    assert auto_update.SKIP_ENV not in __import__("os").environ


def test_source_checkout_never_checks(monkeypatch):
    monkeypatch.delenv(auto_update.SKIP_ENV, raising=False)
    monkeypatch.setattr(auto_update.sys, "frozen", False, raising=False)
    monkeypatch.setattr(auto_update, "check_and_launch", lambda *a, **k: pytest.fail("should not check"))
    assert auto_update.start_update_if_available() is False
