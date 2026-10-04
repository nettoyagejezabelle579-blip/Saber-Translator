"""直排漫畫裡的短句、單字不能被排成橫的。"""

from __future__ import annotations

import numpy as np
from PIL import Image

from src.core import detection
from src.core.detector.data_types import DetectionResult, TextBlock, TextLine
from src.shared import constants


def _box(x1, y1, x2, y2):
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def _lines(*boxes):
    return [{"polygon": _box(*box)} for box in boxes]


def test_square_short_text_follows_vertical_page():
    textlines = [
        _lines((100, 50, 140, 300), (150, 50, 190, 260)),  # 直排長句
        _lines((400, 80, 440, 116)),  # 「あっ」接近正方形
        _lines((500, 400, 530, 428)),  # 「♡」
    ]
    coords = [(100, 50, 190, 300), (400, 80, 440, 116), (500, 400, 530, 428)]
    assert detection.decide_page_directions(textlines, coords, ["v", "h", "h"]) == ["v", "v", "v"]


def test_real_horizontal_line_stays_horizontal_on_vertical_page():
    textlines = [
        _lines((100, 50, 140, 300)),
        _lines((300, 600, 700, 640)),  # 旁白框：明顯細長的橫排
    ]
    coords = [(100, 50, 140, 300), (300, 600, 700, 640)]
    assert detection.decide_page_directions(textlines, coords, ["v", "h"]) == ["v", "h"]


def test_one_long_narration_line_does_not_flip_the_page():
    textlines = [
        _lines((100, 50, 140, 260), (150, 50, 190, 240), (200, 50, 240, 200)),
        _lines((50, 700, 750, 740)),  # 很長的橫排旁白
        _lines((500, 400, 534, 432)),
    ]
    coords = [(100, 50, 240, 260), (50, 700, 750, 740), (500, 400, 534, 432)]
    assert detection.decide_page_directions(textlines, coords, ["v", "h", "h"]) == ["v", "h", "v"]


def test_square_text_follows_horizontal_page():
    textlines = [
        _lines((50, 50, 450, 90), (50, 100, 400, 140)),
        _lines((600, 600, 636, 634)),
    ]
    coords = [(50, 50, 450, 140), (600, 600, 636, 634)]
    assert detection.decide_page_directions(textlines, coords, ["h", "h"]) == ["h", "h"]


def test_page_with_only_short_text_defaults_to_vertical():
    textlines = [_lines((10, 10, 40, 42)), _lines((100, 100, 128, 126))]
    coords = [(10, 10, 40, 42), (100, 100, 128, 126)]
    assert detection.decide_page_directions(textlines, coords, ["h", "v"]) == ["v", "v"]


def test_long_lines_outweigh_short_ones_inside_a_bubble():
    textlines = [_lines((100, 50, 140, 320), (150, 50, 210, 90))]
    assert detection.decide_page_directions(textlines, [(100, 50, 210, 320)], ["h"]) == ["v"]


def test_bubble_without_lines_uses_its_box():
    textlines = [[], []]
    coords = [(0, 0, 40, 200), (300, 300, 330, 330)]
    assert detection.decide_page_directions(textlines, coords, ["v", "h"]) == ["v", "v"]


def test_detection_result_uses_page_directions(monkeypatch):
    blocks = [
        TextBlock(lines=[TextLine(pts=np.array(_box(100, 50, 140, 300)))]),
        TextBlock(lines=[TextLine(pts=np.array(_box(400, 80, 440, 116)))]),
        TextBlock(lines=[TextLine(pts=np.array(_box(200, 600, 700, 640)))]),
    ]
    monkeypatch.setattr(
        detection,
        "_detect_with_optional_saber_refinement",
        lambda *args, **kwargs: DetectionResult(blocks=blocks),
    )
    image = Image.new("RGB", (800, 800), "white")
    result = detection.get_bubble_detection_result_with_auto_directions(image, detector_type="default")
    assert result["auto_directions"] == ["v", "v", "h"]

    monkeypatch.setattr(constants, "PAGE_AWARE_TEXT_DIRECTION", False)
    result = detection.get_bubble_detection_result_with_auto_directions(image, detector_type="default")
    assert result["auto_directions"][1] == "h"
