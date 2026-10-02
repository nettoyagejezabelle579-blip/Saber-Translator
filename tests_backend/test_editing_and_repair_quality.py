"""去字殘點清除、小圖匯入放大、翻譯中可編輯已完成頁面。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from src.backend_v2.content.image_import import ImageImportService
from src.backend_v2.content.page_locks import page_reserved_by_job
from src.core.inpainting import _despeckle_flat_regions


def test_despeckle_removes_leftover_dots_in_white_bubble():
    image = np.full((200, 200, 3), 250, np.uint8)
    image[100, 100] = (120, 120, 120)  # 灰點
    image[90:92, 110:112] = (200, 60, 60)  # 彩點
    mask = np.zeros((200, 200), bool)
    mask[80:120, 80:120] = True
    with Image.fromarray(image) as source:
        cleaned = _despeckle_flat_regions(source, mask)
    result = np.array(cleaned)
    assert (result[80:120, 80:120] == 250).all()


def test_despeckle_keeps_bubble_outline_and_textured_art():
    image = np.full((200, 200, 3), 250, np.uint8)
    image[:, 60:63] = 0  # 氣泡外框穿過清理範圍邊緣
    mask = np.zeros((200, 200), bool)
    mask[80:120, 64:120] = True
    with Image.fromarray(image) as source:
        cleaned = _despeckle_flat_regions(source, mask)
    assert cleaned is None or (np.array(cleaned)[:, 60:63] == 0).all()

    rng = np.random.default_rng(1)
    art = rng.integers(0, 255, (120, 120, 3), dtype=np.uint8)
    art_mask = np.zeros((120, 120), bool)
    art_mask[40:80, 40:80] = True
    with Image.fromarray(art) as source:
        assert _despeckle_flat_regions(source, art_mask) is None


def _png(path: Path, size) -> None:
    Image.new("RGB", size, "white").save(path, format="PNG")


def test_small_pages_are_upscaled_on_import(tmp_path):
    page = tmp_path / "page.upload"
    _png(page, (900, 1280))
    ImageImportService._upscale_small_page(page)
    with Image.open(page) as result:
        assert result.size == (1800, 2560)


def test_large_and_tiny_images_are_not_upscaled(tmp_path):
    for size in ((1700, 2400), (64, 64)):
        page = tmp_path / f"page-{size[0]}.upload"
        _png(page, size)
        ImageImportService._upscale_small_page(page)
        with Image.open(page) as result:
            assert result.size == size


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _FakeConnection:
    """Answers the two queries page_reserved_by_job makes."""

    def __init__(self, job_id, items):
        self.job_id = job_id
        self.items = items
        self.calls = 0

    def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return _Rows([self.job_id] if self.job_id else [])
        return _Rows(self.items)


def test_unlocked_chapter_is_editable():
    assert not page_reserved_by_job(_FakeConnection(None, []), "c", "p1")


def test_finished_page_is_editable_while_job_runs():
    items = [("p1", "completed"), ("p2", "running"), ("p3", "pending")]
    assert not page_reserved_by_job(_FakeConnection("j", items), "c", "p1")
    assert page_reserved_by_job(_FakeConnection("j", items), "c", "p2")
    assert page_reserved_by_job(_FakeConnection("j", items), "c", "p3")


def test_page_outside_job_is_editable_but_chapter_jobs_keep_lock():
    assert not page_reserved_by_job(_FakeConnection("j", [("p2", "running")]), "c", "p9")
    assert page_reserved_by_job(_FakeConnection("j", []), "c", "p1")
