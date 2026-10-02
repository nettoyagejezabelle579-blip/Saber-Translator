"""單獨語氣詞保留、原圖文字顏色、原文字號、MangaOCR 漏字重試、LaMa 純色快速填充、Windows 繁體字型。"""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest
from PIL import Image

from src.shared.sfx_filter import is_standalone_sfx


@pytest.mark.parametrize("text", ["あ", "うん", "あっ…", "はぁはぁ", "んっ♡", "えっ！？", "……", "アァン♡", "ふう"])
def test_standalone_interjections_are_kept(text):
    assert is_standalone_sfx(text, {})


@pytest.mark.parametrize("text", ["はい", "いい", "ダメ", "やめて", "あ、あの…", "ふふ", "いや", "うそ", "気持ちいい", ""])
def test_real_speech_is_translated(text):
    assert not is_standalone_sfx(text, {})


@pytest.mark.parametrize("text", [
    "ぴゅっ♡", "どぴゅ♡", "ドピュッ", "びゅるる", "ぐちゅ", "ドキドキ", "ぱんぱん",
    "くちゅくちゅ", "ビクッ", "ギクッ", "ずぶずぶ", "ぎゅっ",
])
def test_standalone_onomatopoeia_is_kept(text):
    assert is_standalone_sfx(text, {})


@pytest.mark.parametrize("text", [
    "いやいや", "もっともっと", "ちょっと", "パンツ", "ごめん", "じょうず", "だって",
    "すごい", "ばか",
])
def test_short_words_that_look_like_sfx_are_translated(text):
    assert not is_standalone_sfx(text, {})


def test_sfx_switch_can_be_disabled():
    assert not is_standalone_sfx("あ", {"SABER_KEEP_STANDALONE_SFX": "0"})


def _vertical_line(x1, y1, x2, y2):
    return {"polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], "direction": "v", "confidence": 1.0}


def test_text_color_is_measured_from_pixels():
    from src.core.text_color import measure_bubble_color

    image = np.full((200, 200, 3), 255, np.uint8)
    image[40:160, 90:110] = (200, 30, 40)  # 紅色筆畫
    result = measure_bubble_color(image, (60, 20, 140, 180), [_vertical_line(85, 35, 115, 165)])
    assert result["bg_color"] == [255, 255, 255]
    assert result["fg_color"] == [200, 30, 40]
    assert result["confidence"] > 0.5


def test_near_black_text_snaps_to_black():
    from src.core.text_color import measure_bubble_color

    image = np.full((120, 120, 3), 250, np.uint8)
    image[20:100, 55:65] = 30
    result = measure_bubble_color(image, (30, 10, 90, 110), [_vertical_line(50, 15, 70, 105)])
    assert result["fg_color"] == [0, 0, 0]
    assert result["bg_color"] == [255, 255, 255]


def test_source_font_size_caps_auto_size():
    from src.core.rendering import calculate_auto_font_size, estimate_source_font_size

    lines = [_vertical_line(100, 0, 140, 300), _vertical_line(50, 0, 90, 300)]
    assert estimate_source_font_size(lines) == 34
    free = calculate_auto_font_size("短句", 300, 300, "vertical")
    matched = calculate_auto_font_size("短句", 300, 300, "vertical", textlines=lines)
    assert free > 34
    assert matched == 34


def test_source_size_never_forces_overflow():
    from src.core.rendering import calculate_auto_font_size

    lines = [_vertical_line(0, 0, 60, 100)]
    long_text = "這是一段比原文長很多很多的中文譯文" * 3
    assert calculate_auto_font_size(long_text, 100, 100, "vertical", textlines=lines) < 51


@pytest.fixture
def ocr_module(monkeypatch):
    # 測試環境不一定裝了 manga_ocr；這裡只測分段邏輯，識別本身用假函式取代
    try:
        import manga_ocr  # noqa: F401
    except ImportError:
        stub = types.ModuleType("manga_ocr")
        stub.MangaOcr = object
        monkeypatch.setitem(sys.modules, "manga_ocr", stub)
        for name in ("src.core.ocr", "src.interfaces.manga_ocr_interface"):
            monkeypatch.delitem(sys.modules, name, raising=False)
    from src.core import ocr

    return ocr


def test_manga_ocr_rereads_dense_bubbles_in_chunks(monkeypatch, ocr_module):
    ocr = ocr_module

    image = Image.new("RGB", (400, 300), "white")
    lines = [_vertical_line(x, 10, x + 30, 290) for x in (340, 290, 240, 190, 140, 90)]

    def fake_recognize(crop):
        # 整個氣泡 → 只認出一點；分段 → 每段都完整
        return "あ" if crop.size[0] > 200 else "わたしのこえ"

    monkeypatch.setattr(ocr, "recognize_japanese_text", fake_recognize)
    results = ocr._recognize_with_manga_ocr_results(image, [(80, 0, 380, 300)], [lines])
    assert results[0].text == "わたしのこえ" * 3


def test_manga_ocr_keeps_good_whole_bubble_result(monkeypatch, ocr_module):
    ocr = ocr_module

    image = Image.new("RGB", (400, 300), "white")
    lines = [_vertical_line(x, 10, x + 30, 100) for x in (340, 290, 240)]
    calls = []

    def fake_recognize(crop):
        calls.append(crop.size)
        return "これでぜんぶよめた"

    monkeypatch.setattr(ocr, "recognize_japanese_text", fake_recognize)
    results = ocr._recognize_with_manga_ocr_results(image, [(200, 0, 380, 120)], [lines])
    assert results[0].text == "これでぜんぶよめた"
    assert len(calls) == 1


def test_lama_flat_regions_skip_the_model(monkeypatch):
    from src.interfaces import lama_interface

    def explode():
        raise AssertionError("LaMa should not load for flat bubbles")

    monkeypatch.setattr(
        "src.interfaces.lama_mpe_interface.get_lama_mpe_inpainter", explode
    )
    source = np.full((200, 200, 3), 252, np.uint8)
    source[80:120, 90:110] = 0  # 白底上的黑字
    mask = np.zeros((200, 200), np.uint8)
    mask[75:125, 85:115] = 255
    with Image.fromarray(source) as image, Image.fromarray(mask) as mask_image:
        result = lama_interface._clean_lama_regions(image, mask_image, "lama_mpe", False)
    output = np.array(result)
    assert (output[75:125, 85:115] == 252).all()


def test_flat_color_rejects_textured_background():
    from src.interfaces.lama_interface import _flat_surrounding_color

    rng = np.random.default_rng(0)
    crop = rng.integers(0, 255, (60, 60, 3), dtype=np.uint8)
    local = np.zeros((60, 60), bool)
    local[25:35, 25:35] = True
    assert _flat_surrounding_color(crop, local, local, 6.0) is None


def test_windows_jhenghei_becomes_default_font(monkeypatch, tmp_path):
    from src.backend_v2.storage import font_files
    from src.backend_v2.storage.defaults import DEFAULT_FONT_ID

    fonts_dir = tmp_path / "Fonts"
    fonts_dir.mkdir()
    (fonts_dir / "msjhbd.ttc").write_bytes(b"fake")
    monkeypatch.setenv("WINDIR", str(tmp_path))
    catalog = font_files.bundled_font_files()
    default = next(font for font in catalog if font.id == DEFAULT_FONT_ID)
    assert default.path.name == "msjhbd.ttc"
    assert default.display_name == "微軟正黑體 粗體"


def test_without_windows_fonts_default_is_unchanged(monkeypatch):
    from src.backend_v2.storage import font_files
    from src.backend_v2.storage.defaults import DEFAULT_FONT_ID

    monkeypatch.delenv("WINDIR", raising=False)
    monkeypatch.delenv("SystemRoot", raising=False)
    default = next(font for font in font_files.bundled_font_files() if font.id == DEFAULT_FONT_ID)
    assert "SourceHanSansK" in default.path.name
