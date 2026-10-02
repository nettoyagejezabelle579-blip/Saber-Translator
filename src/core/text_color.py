"""
直接量測原圖文字顏色（自動文字顏色用）

48px OCR 的顏色預測要再跑一次完整的 OCR 束搜尋，在 CPU 上很慢，結果也常偏灰。
這裡改成看像素：
1. 文字區域 = 該氣泡所有文字行多邊形；背景 = 文字區域外圍一圈的中位數顏色。
2. 文字區域內與背景差距夠大的像素視為筆畫，取差距最大的那部分（避開抗鋸齒邊緣）的中位數。
3. 接近純黑／純白的結果直接定為 #000000／#FFFFFF。
"""

from __future__ import annotations

from typing import Any, Sequence

import cv2
import numpy as np
from PIL import Image

_MIN_STROKE_PIXELS = 12


def _text_mask(shape, offset, textlines, box) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    ox, oy = offset
    polygons = []
    for line in textlines or []:
        points = np.asarray(line.get("polygon") or [], dtype=np.int32).reshape(-1, 2)
        if len(points) >= 3:
            polygons.append(points - [ox, oy])
    if polygons:
        cv2.fillPoly(mask, polygons, 255)
    else:
        x1, y1, x2, y2 = box
        mask[y1 - oy:y2 - oy, x1 - ox:x2 - ox] = 255
    return mask


def _snap(color: np.ndarray) -> list[int]:
    rgb = [int(round(float(c))) for c in color]
    if max(rgb) <= 45:
        return [0, 0, 0]
    if min(rgb) >= 220:
        return [255, 255, 255]
    return rgb


def measure_bubble_color(
    image: np.ndarray,
    coords: Sequence[int],
    textlines: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = (int(v) for v in coords)
    margin = max(6, round(0.08 * max(x2 - x1, y2 - y1)))
    cx1, cy1 = max(0, x1 - margin), max(0, y1 - margin)
    cx2, cy2 = min(width, x2 + margin), min(height, y2 + margin)
    empty = {"fg_color": None, "bg_color": None, "confidence": 0.0}
    if cx2 <= cx1 or cy2 <= cy1:
        return empty
    crop = image[cy1:cy2, cx1:cx2].astype(np.int16)
    inside = _text_mask(crop.shape[:2], (cx1, cy1), textlines, (x1, y1, x2, y2))
    if not inside.any():
        return empty

    thickness = max(3, min(12, round(0.06 * min(x2 - x1, y2 - y1))))
    outer = cv2.dilate(inside, np.ones((2 * thickness + 1,) * 2, np.uint8))
    near = cv2.dilate(inside, np.ones((3, 3), np.uint8))
    ring = (outer > 0) & (near == 0)
    ring_pixels = crop[ring]
    text_pixels = crop[inside > 0]
    if len(ring_pixels) >= _MIN_STROKE_PIXELS:
        background = np.median(ring_pixels, axis=0)
    else:
        brightness = text_pixels.sum(axis=1)
        background = np.median(text_pixels[brightness >= np.percentile(brightness, 50)], axis=0)

    distance = np.linalg.norm(text_pixels - background, axis=1)
    threshold = max(40.0, 0.5 * float(np.percentile(distance, 98)))
    strokes = distance >= threshold
    if int(strokes.sum()) < _MIN_STROKE_PIXELS:
        return {"fg_color": None, "bg_color": _snap(background), "confidence": 0.0}
    stroke_distance = distance[strokes]
    core = text_pixels[strokes][stroke_distance >= np.percentile(stroke_distance, 60)]
    foreground = np.median(core, axis=0)
    confidence = float(min(1.0, np.linalg.norm(foreground - background) / 220.0))
    return {
        "fg_color": _snap(foreground),
        "bg_color": _snap(background),
        "confidence": round(confidence, 4),
    }


def measure_bubble_colors(
    image: Image.Image,
    bubble_coords: Sequence[Sequence[int]],
    textlines_per_bubble: Sequence[list[dict[str, Any]] | None],
) -> list[dict[str, Any]]:
    array = np.asarray(image.convert("RGB") if image.mode != "RGB" else image)
    return [
        measure_bubble_color(array, coords, textlines)
        for coords, textlines in zip(bubble_coords, textlines_per_bubble)
    ]
