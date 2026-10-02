import unittest

import cv2
import numpy as np

from src.core.detector.bubble_regions import compute_bubble_labels
from src.core.detector.data_types import TextLine
from src.core.detector.textline_merge import merge_textlines


def _vertical_line(x, y1, y2, width=20):
    return TextLine(
        pts=np.array([[x, y1], [x + width, y1], [x + width, y2], [x, y2]]),
        confidence=0.9,
    )


def _draw_text_column(image, x, y1, y2, width=20):
    for y in range(y1 + 2, y2 - 2, width + 4):
        cv2.rectangle(image, (x + 3, y), (x + width - 3, y + width - 4), (0, 0, 0), 2)


def _two_bubble_page():
    """两个紧挨着的白色气泡，中间只隔着黑色描边。"""
    image = np.full((400, 400, 3), 90, dtype=np.uint8)  # 灰色画面背景
    cv2.ellipse(image, (125, 200), (45, 120), 0, 0, 360, (255, 255, 255), -1)
    cv2.ellipse(image, (125, 200), (45, 120), 0, 0, 360, (0, 0, 0), 3)
    cv2.ellipse(image, (222, 200), (45, 120), 0, 0, 360, (255, 255, 255), -1)
    cv2.ellipse(image, (222, 200), (45, 120), 0, 0, 360, (0, 0, 0), 3)
    columns = [(140, 150, 250), (112, 150, 250), (184, 150, 250)]
    for x, y1, y2 in columns:
        _draw_text_column(image, x, y1, y2)
    lines = [_vertical_line(x, y1, y2) for x, y1, y2 in columns]
    return image, lines


class BubbleAwareMergeTests(unittest.TestCase):
    def test_labels_distinguish_adjacent_bubbles(self):
        image, lines = _two_bubble_page()
        labels = compute_bubble_labels(image, lines)
        self.assertIsNotNone(labels[0])
        self.assertEqual(labels[0], labels[1])
        self.assertIsNotNone(labels[2])
        self.assertNotEqual(labels[0], labels[2])

    def test_geometry_only_merge_joins_adjacent_bubbles(self):
        _, lines = _two_bubble_page()
        blocks = merge_textlines(lines, 400, 400)
        self.assertEqual(len(blocks), 1)

    def test_bubble_aware_merge_keeps_bubbles_separate(self):
        image, lines = _two_bubble_page()
        blocks = merge_textlines(lines, 400, 400, image=image)
        self.assertEqual(len(blocks), 2)
        sizes = sorted(len(block.lines) for block in blocks)
        self.assertEqual(sizes, [1, 2])

    def test_text_on_artwork_falls_back_to_geometry(self):
        image = np.full((400, 400, 3), 60, dtype=np.uint8)
        lines = [_vertical_line(150, 120, 280), _vertical_line(122, 120, 280)]
        self.assertEqual(compute_bubble_labels(image, lines), [None, None])
        blocks = merge_textlines(lines, 400, 400, image=image)
        self.assertEqual(len(blocks), 1)


if __name__ == "__main__":
    unittest.main()
