from __future__ import annotations

from unittest import mock

import cv2
import numpy as np
from PIL import Image

from src.core.inpainting import inpaint_bubbles

BUBBLE = (238, 232, 214)  # 扫描件常见的米黄色气泡


def _page_with_text(background):
    image = background.copy()
    text = np.zeros(image.shape[:2], dtype=np.uint8)
    cv2.putText(text, "ABC", (40, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.4, 255, 3, cv2.LINE_AA)
    alpha = (text.astype(np.float32) / 255.0)[..., None]
    image = (image * (1 - alpha)).astype(np.uint8)  # 黑字 + 抗锯齿灰边
    precise = np.where(text > 128, 255, 0).astype(np.uint8)  # 模型掩膜只覆盖字芯
    return image, precise, text


def _run(image, precise, fill="#ffffff"):
    source = Image.fromarray(image)
    try:
        result = inpaint_bubbles(
            source,
            [[20, 30, 180, 110]],
            method="solid",
            fill_color=fill,
            precise_mask=precise,
            mask_dilate_size=0,
            mask_box_expand_ratio=0,
        )
        try:
            return np.asarray(result).copy()
        finally:
            result.close()
    finally:
        source.close()


def test_uniform_bubble_uses_sampled_color_and_removes_halo():
    background = np.full((140, 200, 3), BUBBLE, dtype=np.uint8)
    image, precise, text = _page_with_text(background)
    out = _run(image, precise)
    stroke_area = text > 0
    diff = np.abs(out[stroke_area].astype(int) - np.array(BUBBLE)).max(axis=1)
    # 原实现会留下纯白色块和灰色描边；现在几乎全部恢复为气泡底色
    assert np.mean(diff <= 6) > 0.9
    assert not np.any(np.all(out == [255, 255, 255], axis=2))


def test_textured_background_is_inpainted_instead_of_flat_block():
    ramp = np.tile(np.linspace(80, 230, 200, dtype=np.float32), (140, 1))
    background = np.repeat(ramp[..., None], 3, axis=2).astype(np.uint8)
    image, precise, _ = _page_with_text(background)
    out = _run(image, precise)
    filled = precise > 0
    expected = background[filled].astype(int)
    assert np.abs(out[filled].astype(int) - expected).mean() < 25
    assert not np.any(np.all(out == [255, 255, 255], axis=2))


def test_explicit_contrasting_color_is_respected():
    background = np.full((140, 200, 3), BUBBLE, dtype=np.uint8)
    image, precise, _ = _page_with_text(background)
    out = _run(image, precise, fill="#ff0000")
    assert np.all(out[precise > 0] == [255, 0, 0])


def test_can_be_disabled():
    background = np.full((140, 200, 3), BUBBLE, dtype=np.uint8)
    image, precise, _ = _page_with_text(background)
    with mock.patch("src.shared.constants.SMART_SOLID_FILL", False):
        out = _run(image, precise)
    assert np.all(out[precise > 0] == [255, 255, 255])
