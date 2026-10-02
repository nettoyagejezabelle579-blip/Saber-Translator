import unittest
from unittest import mock

import numpy as np

from src.core.detector.backends.default_backend import DefaultBackend
from src.core.detector.data_types import TextLine


def _backend(detect_size=1536):
    backend = DefaultBackend.__new__(DefaultBackend)
    backend.detect_size = detect_size
    backend.text_threshold = 0.5
    backend.unclip_ratio = 2.2
    return backend


class DefaultPreprocessTests(unittest.TestCase):
    def test_large_image_ratio_maps_back_to_original(self):
        backend = _backend(1536)
        image = np.zeros((3000, 2000, 3), dtype=np.uint8)
        resized, ratio, pad_w, pad_h = backend._preprocess_image(image)
        self.assertAlmostEqual(ratio, 1536 / 3000, places=4)
        self.assertEqual(resized.shape[0] - pad_h, 1536)
        self.assertEqual(resized.shape[0] % 256, 0)
        self.assertEqual(resized.shape[1] % 256, 0)
        self.assertEqual(resized.shape[1] - pad_w, round(2000 * 1536 / 3000))

    def test_small_image_keeps_original_path(self):
        backend = _backend(1536)
        image = np.zeros((800, 600, 3), dtype=np.uint8)
        resized, ratio, _, _ = backend._preprocess_image(image)
        self.assertAlmostEqual(ratio, 1536 / 800, places=4)


class FaintLineRescueTests(unittest.TestCase):
    def _prob_map(self):
        db = np.zeros((1, 1, 512, 512), dtype=np.float32)
        db[0, 0, 100:120, 100:220] = 0.9   # 正常文本行
        db[0, 0, 300:318, 100:200] = 0.45  # 浅色文本行（低于 0.5 阈值）
        db[0, 0, 400:404, 400:404] = 0.45  # 噪点
        return db

    def test_recovers_faint_text_without_duplicates(self):
        backend = _backend()
        existing = [TextLine(pts=np.array([[95, 95], [225, 95], [225, 125], [95, 125]]))]
        rescued = backend._rescue_faint_lines(
            self._prob_map(), existing, 512, 512, 1.0, 1.0
        )
        self.assertEqual(len(rescued), 1)
        x1, y1, x2, y2 = rescued[0].xyxy
        self.assertTrue(280 <= y1 <= 300 and 318 <= y2 <= 340)

    def test_can_be_disabled(self):
        backend = _backend()
        with mock.patch("src.shared.constants.DEFAULT_DETECTOR_RESCUE_THRESHOLD", 0):
            self.assertEqual(
                backend._rescue_faint_lines(self._prob_map(), [], 512, 512, 1.0, 1.0),
                [],
            )


if __name__ == "__main__":
    unittest.main()
