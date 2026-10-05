"""單獨語氣詞保留、原圖文字顏色、原文字號、MangaOCR 漏字重試、LaMa 純色快速填充、Windows 繁體字型。"""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest
from PIL import Image

from src.shared.sfx_filter import is_standalone_sfx

_ON = {"SABER_KEEP_STANDALONE_SFX": "1"}


@pytest.mark.parametrize("text", ["あ", "うん", "あっ…", "はぁはぁ", "んっ♡", "えっ！？", "……", "アァン♡", "ふう"])
def test_standalone_interjections_are_kept(text):
    assert is_standalone_sfx(text, _ON)


@pytest.mark.parametrize("text", ["はい", "いい", "ダメ", "やめて", "あ、あの…", "ふふ", "いや", "うそ", "気持ちいい", ""])
def test_real_speech_is_translated(text):
    assert not is_standalone_sfx(text, _ON)


@pytest.mark.parametrize("text", [
    "ぴゅっ♡", "どぴゅ♡", "ドピュッ", "びゅるる", "ぐちゅ", "ドキドキ", "ぱんぱん",
    "くちゅくちゅ", "ビクッ", "ギクッ", "ずぶずぶ", "ぎゅっ",
])
def test_standalone_onomatopoeia_is_kept(text):
    assert is_standalone_sfx(text, _ON)


@pytest.mark.parametrize("text", [
    "いやいや", "もっともっと", "ちょっと", "パンツ", "ごめん", "じょうず", "だって",
    "すごい", "ばか",
])
def test_short_words_that_look_like_sfx_are_translated(text):
    assert not is_standalone_sfx(text, _ON)


def test_sfx_switch_can_be_disabled():
    assert not is_standalone_sfx("あ", {"SABER_KEEP_STANDALONE_SFX": "0"})


def test_sfx_rule_is_off_by_default():
    assert not is_standalone_sfx("あ", {})
    assert not is_standalone_sfx("ドキドキ", {})


def _vertical_line(x1, y1, x2, y2):
    return {"polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], "direction": "v", "confidence": 1.0}


def _draw_column(bg, fill, stroke, stroke_width, size=60):
    from PIL import ImageDraw, ImageFont

    font = ImageFont.truetype(
        "src/backend_v2/resources/fonts/思源黑体SourceHanSansK-Bold.TTF", size
    )
    image = Image.new("RGB", (220, 420), bg)
    draw = ImageDraw.Draw(image)
    for index, char in enumerate("びゅっ"):
        draw.text((80, 40 + index * 90), char, font=font, fill=fill,
                  stroke_width=stroke_width, stroke_fill=stroke)
    return np.asarray(image)


@pytest.mark.parametrize(("bg", "fill", "stroke", "width"), [
    ((209, 149, 134), (255, 36, 255), (255, 255, 255), 6),   # 粉紅字＋白邊，膚色背景
    ((209, 149, 134), (140, 40, 200), (255, 255, 255), 6),   # 紫字＋白邊
    ((40, 40, 40), (255, 255, 255), (0, 0, 0), 5),           # 白字＋黑邊，暗背景
    ((255, 255, 255), (200, 30, 60), (255, 255, 255), 0),    # 紅字，白底
])
def test_outlined_colored_text_reports_fill_not_outline(bg, fill, stroke, width):
    from src.core.text_color import measure_bubble_color

    image = _draw_column(bg, fill, stroke, width)
    line = _vertical_line(70, 30, 150, 330)
    assert measure_bubble_color(image, (60, 20, 160, 340), [line])["fg_color"] == list(fill)


def _draw_outlined_block(bg, fill, stroke, stroke_width, glow=None, text="これは", size=56):
    """多欄直書，可加外光暈：字縫間露出背景（使用者回報的粉紅字白框案例）。"""
    from PIL import ImageDraw, ImageFilter, ImageFont

    font = ImageFont.truetype(
        "src/backend_v2/resources/fonts/思源黑体SourceHanSansK-Bold.TTF", size
    )
    image = Image.new("RGB", (300, 360), bg)
    if glow is not None:
        halo = Image.new("L", image.size, 0)
        halo_draw = ImageDraw.Draw(halo)
        for column in range(3):
            for row, char in enumerate(text):
                halo_draw.text((200 - column * 75, 30 + row * 95), char, font=font, fill=255,
                               stroke_width=stroke_width + 8, stroke_fill=255)
        halo = halo.filter(ImageFilter.GaussianBlur(6))
        image.paste(Image.new("RGB", image.size, glow), mask=halo)
    draw = ImageDraw.Draw(image)
    for column in range(3):
        for row, char in enumerate(text):
            draw.text((200 - column * 75, 30 + row * 95), char, font=font, fill=fill,
                      stroke_width=stroke_width, stroke_fill=stroke)
    lines = [_vertical_line(190 - column * 75, 20, 270 - column * 75, 330) for column in range(3)]
    return np.asarray(image), lines


def _close(measured, expected, tolerance=40):
    return measured is not None and all(abs(a - b) <= tolerance for a, b in zip(measured, expected))


@pytest.mark.parametrize(("bg", "fill", "stroke", "width", "glow", "text"), [
    # 使用者回報：粉紅字＋粗白框＋粉紅光暈，灰色畫面（以前變成黑字）
    ((90, 85, 88), (252, 89, 153), (255, 255, 255), 6, (240, 200, 215), "これは"),
    ((183, 180, 180), (252, 89, 153), (255, 255, 255), 6, (232, 210, 214), "あんた"),
    # 黑字白框放在灰色畫面上
    ((110, 110, 110), (0, 0, 0), (255, 255, 255), 6, None, "これは"),
    # 白字黑框放在彩色畫面上
    ((60, 120, 200), (255, 255, 255), (0, 0, 0), 5, None, "あんた"),
    # 一般黑字白底，有很多封閉的洞（口、回、日）
    ((255, 255, 255), (0, 0, 0), (0, 0, 0), 0, None, "回口日"),
    # 白字黑底
    ((0, 0, 0), (255, 255, 255), (255, 255, 255), 0, None, "回口日"),
])
def test_text_color_follows_layers_from_outside_in(bg, fill, stroke, width, glow, text):
    from src.core.text_color import measure_bubble_color

    image, lines = _draw_outlined_block(bg, fill, stroke, width, glow, text)
    measured = measure_bubble_color(image, (30, 20, 280, 330), lines)["fg_color"]
    assert _close(measured, fill), (measured, fill)


def test_text_color_on_screentone():
    from PIL import ImageDraw, ImageFont
    from src.core.text_color import measure_bubble_color

    image = Image.new("RGB", (240, 360), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, 360, 6):
        for x in range(0, 240, 6):
            draw.ellipse((x, y, x + 2, y + 2), fill=(90, 90, 90))
    font = ImageFont.truetype("src/backend_v2/resources/fonts/思源黑体SourceHanSansK-Bold.TTF", 56)
    for row, char in enumerate("ちがう"):
        draw.text((90, 30 + row * 95), char, font=font, fill=(0, 0, 0),
                  stroke_width=5, stroke_fill=(255, 255, 255))
    measured = measure_bubble_color(
        np.asarray(image), (70, 20, 170, 330), [_vertical_line(80, 20, 160, 330)]
    )["fg_color"]
    assert measured == [0, 0, 0]


def test_light_text_gets_dark_outline():
    from src.core.text_color import contrast_stroke_color

    assert contrast_stroke_color([255, 255, 255]) == "#000000"
    assert contrast_stroke_color([255, 36, 255]) == "#FFFFFF"
    assert contrast_stroke_color([0, 0, 0]) == "#FFFFFF"


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
    # 文字行寬 40 → 原文字號 40；譯文以原文字號為目標，不會被填滿整個框而變大
    assert estimate_source_font_size(lines) == 40
    free = calculate_auto_font_size("短句", 300, 300, "vertical")
    matched = calculate_auto_font_size("短句", 300, 300, "vertical", textlines=lines)
    assert free > 40
    assert matched == 40


def test_auto_size_keeps_original_size_for_typical_bubbles():
    from src.core.rendering import calculate_auto_font_size

    # 原文 3 列、字號 40：中文譯文多一列也維持原文大小（允許向氣泡留白溢出 30%）
    lines = [_vertical_line(100, 10, 140, 330), _vertical_line(55, 10, 95, 300),
             _vertical_line(10, 10, 50, 250)]
    for text in ("要、要被吸出來了……", "尿道裡殘留的也全部被吸出來了……", "咻～"):
        assert calculate_auto_font_size(text, 140, 330, "vertical", textlines=lines) == 40


def test_large_text_is_not_capped_at_80px():
    from src.core.rendering import calculate_auto_font_size

    big = [_vertical_line(0, 0, 110, 500)]
    assert calculate_auto_font_size("咻～♡", 120, 520, "vertical", textlines=big) == 110


def test_horizontal_fit_uses_width_for_characters_per_line():
    from src.core.rendering import calculate_auto_font_size

    # 寬 400、高 60 的橫排框：一行 10 字 → 約 38px，而不是被當成直排算得很小
    assert calculate_auto_font_size("一二三四五六七八九十", 400, 60, "horizontal") >= 36


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
    monkeypatch.setattr(ocr, "recognize_japanese_text_best", fake_recognize)
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
    monkeypatch.setattr(ocr, "recognize_japanese_text_best", fake_recognize)
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


def test_supersampled_text_keeps_size_and_background(monkeypatch):
    from src.core import rendering
    from src.core.config_models import BubbleState
    from src.shared import constants

    state = BubbleState(
        translated_text="好舒服♡", coords=(20, 20, 140, 260), font_size=26,
        font_family=constants.DEFAULT_FONT_RELATIVE_PATH, text_direction="vertical",
        text_color="#000000", stroke_enabled=True, stroke_color="#FFFFFF", stroke_width=3,
    )
    monkeypatch.setattr(constants, "TEXT_SUPERSAMPLE", 2)
    image = Image.new("RGB", (160, 280), (235, 200, 180))
    rendering.render_bubbles_unified(image, [state])
    pixels = np.asarray(image)
    assert image.size == (160, 280)
    assert (pixels[:10, :10] == (235, 200, 180)).all()  # 背景不被縮放影響
    assert (pixels.sum(axis=2) < 100).sum() > 200  # 有黑色文字


def test_supersampling_skips_huge_pages(monkeypatch):
    from src.core import rendering
    from src.shared import constants

    calls = []
    monkeypatch.setattr(constants, "TEXT_SUPERSAMPLE", 2)
    monkeypatch.setattr(rendering, "_SUPERSAMPLE_MAX_PIXELS", 100)
    monkeypatch.setattr(rendering, "_render_bubbles_direct", lambda image, states: calls.append(image.size) or image)
    image = Image.new("RGB", (50, 50))
    rendering.render_bubbles_unified(image, [object()])
    assert calls == [(50, 50)]
