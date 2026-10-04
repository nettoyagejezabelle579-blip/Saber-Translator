"""同一個氣泡不被拆開、不同氣泡不被合併、漏掉的文字行補回氣泡。"""

from __future__ import annotations

import numpy as np
from PIL import Image

from src.core.detector.data_types import DetectionResult, TextBlock, TextLine
from src.core.detector.refinement import consolidate_with_reference_blocks


def _line(x1, y1, x2, y2):
    return TextLine(pts=np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]]))


def _block(*lines):
    return TextBlock(lines=list(lines))


IMAGE = Image.new("RGB", (800, 800), "white")


def test_one_bubble_split_in_two_is_merged():
    left = _block(_line(100, 100, 130, 300))
    right = _block(_line(150, 100, 180, 280))
    bubble = _block(_line(80, 80, 200, 320))  # 參考氣泡
    result = consolidate_with_reference_blocks(
        DetectionResult(blocks=[left, right], raw_lines=left.lines + right.lines),
        DetectionResult(blocks=[bubble]),
        IMAGE,
    )
    assert len(result.blocks) == 1
    assert len(result.blocks[0].lines) == 2


def test_separate_bubbles_stay_separate():
    first = _block(_line(100, 100, 130, 300))
    second = _block(_line(500, 100, 530, 300))
    bubbles = [_block(_line(80, 80, 200, 320)), _block(_line(480, 80, 600, 320))]
    result = consolidate_with_reference_blocks(
        DetectionResult(blocks=[first, second], raw_lines=first.lines + second.lines),
        DetectionResult(blocks=bubbles),
        IMAGE,
    )
    assert len(result.blocks) == 2


def test_dropped_line_is_added_back_to_its_bubble():
    kept = _block(_line(150, 100, 180, 300))
    dropped = _line(100, 100, 130, 200)  # 同一氣泡的第二列被漏掉
    bubble = _block(_line(80, 80, 200, 320))
    result = consolidate_with_reference_blocks(
        DetectionResult(blocks=[kept], raw_lines=kept.lines + [dropped]),
        DetectionResult(blocks=[bubble]),
        IMAGE,
    )
    assert len(result.blocks) == 1
    assert len(result.blocks[0].lines) == 2


def test_far_away_stray_line_is_not_glued_to_a_bubble():
    kept = _block(_line(150, 100, 180, 300))
    stray = _line(600, 600, 630, 700)  # 遠處的雜訊、不在任何氣泡內
    bubble = _block(_line(80, 80, 200, 320))
    result = consolidate_with_reference_blocks(
        DetectionResult(blocks=[kept], raw_lines=kept.lines + [stray]),
        DetectionResult(blocks=[bubble]),
        IMAGE,
    )
    assert len(result.blocks) == 1
    assert len(result.blocks[0].lines) == 1


def test_vertical_and_horizontal_text_in_one_region_are_not_merged():
    column = _block(_line(100, 100, 130, 300))
    row = _block(_line(140, 290, 300, 310))
    region = _block(_line(80, 80, 320, 320))
    result = consolidate_with_reference_blocks(
        DetectionResult(blocks=[column, row], raw_lines=column.lines + row.lines),
        DetectionResult(blocks=[region]),
        IMAGE,
    )
    assert len(result.blocks) == 2
