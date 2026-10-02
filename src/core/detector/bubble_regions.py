"""
气泡区域标注（用于防止相邻气泡的文本行被合并）

思路：漫画对白气泡通常是被深色描边包围的浅色区域。对浅色像素做连通域标注后，
同一气泡内的文字间隙属于同一个连通域，而两个相邻气泡会被各自的描边隔开，
落在不同的连通域里。每个文本行取其多边形内面积占比最大的浅色连通域作为
"气泡编号"；两条文本行编号不同则说明它们处在不同的气泡里，不应合并。

无法可靠判断的情况（深色气泡、图上文字、连通域覆盖大半张图等）返回 None，
此时完全退回原有的几何合并规则，因此不会比原来更差。
"""

import logging
from typing import List, Optional, Sequence

import cv2
import numpy as np

logger = logging.getLogger("BubbleRegions")

# 浅色背景阈值（灰度），低于它视为描边/文字/画面
_BRIGHT_THRESHOLD = 180
# 标注时的像素预算，超过时先缩小以减少 CPU 开销（按面积而非最长边，
# 这样长条漫画缩小后气泡描边依然清晰）
_LABEL_MAX_PIXELS = 4_000_000
# 连通域占整图面积超过此比例时视为页面背景/大片留白，不作为气泡依据
_MAX_BUBBLE_AREA_RATIO = 0.35
# 文本行内浅色像素占比低于此值时视为非白底文字（例如图上文字）
_MIN_BRIGHT_FRACTION = 0.15
# 主导连通域在文本行内浅色像素中的最低占比
_MIN_DOMINANT_FRACTION = 0.5


def compute_bubble_labels(
    image_bgr: np.ndarray,
    textlines: Sequence,
) -> List[Optional[int]]:
    """为每条文本行计算所属气泡编号，无法判断时为 None。"""
    if image_bgr is None or not len(textlines):
        return [None] * len(textlines)

    im_h, im_w = image_bgr.shape[:2]
    if im_h <= 0 or im_w <= 0:
        return [None] * len(textlines)

    scale = min(1.0, (_LABEL_MAX_PIXELS / float(im_h * im_w)) ** 0.5)
    if image_bgr.ndim == 3:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_bgr
    if scale < 1.0:
        gray = cv2.resize(
            gray,
            (max(1, int(round(im_w * scale))), max(1, int(round(im_h * scale)))),
            interpolation=cv2.INTER_AREA,
        )

    bright = (gray >= _BRIGHT_THRESHOLD).astype(np.uint8)
    # 4 连通：避免细描边在对角方向“漏”过去把两个气泡连起来
    num_labels, label_map, stats, _ = cv2.connectedComponentsWithStats(
        bright, connectivity=4
    )
    if num_labels <= 1:
        return [None] * len(textlines)

    total_area = float(label_map.shape[0] * label_map.shape[1])
    areas = stats[:, cv2.CC_STAT_AREA]

    labels: List[Optional[int]] = []
    for line in textlines:
        labels.append(
            _label_for_line(line, label_map, areas, total_area, scale)
        )
    return labels


def _label_for_line(line, label_map, areas, total_area, scale) -> Optional[int]:
    pts = np.asarray(line.pts, dtype=np.float32) * scale
    pts = np.rint(pts).astype(np.int32)
    lh, lw = label_map.shape[:2]
    x1 = max(0, int(pts[:, 0].min()))
    y1 = max(0, int(pts[:, 1].min()))
    x2 = min(lw, int(pts[:, 0].max()) + 1)
    y2 = min(lh, int(pts[:, 1].max()) + 1)
    if x2 <= x1 or y2 <= y1:
        return None

    poly_mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
    cv2.fillPoly(poly_mask, [pts - np.array([x1, y1], dtype=np.int32)], 1)
    inside = poly_mask.astype(bool)
    n_inside = int(inside.sum())
    if n_inside == 0:
        return None

    crop_labels = label_map[y1:y2, x1:x2][inside]
    crop_labels = crop_labels[crop_labels > 0]
    if crop_labels.size < max(4, _MIN_BRIGHT_FRACTION * n_inside):
        return None

    # 忽略字内封闭的小空白（如“口”字中间），只看足够大的连通域
    char_size = max(1.0, float(getattr(line, 'font_size', 1)) * scale)
    min_component_area = 2.0 * char_size * char_size
    counts = np.bincount(crop_labels)
    candidates = np.nonzero(counts)[0]
    candidates = [c for c in candidates if areas[c] >= min_component_area]
    if not candidates:
        return None
    dominant = max(candidates, key=lambda c: counts[c])
    if counts[dominant] < _MIN_DOMINANT_FRACTION * crop_labels.size:
        return None
    if areas[dominant] > _MAX_BUBBLE_AREA_RATIO * total_area:
        return None
    return int(dominant)


def labels_conflict(label_a: Optional[int], label_b: Optional[int]) -> bool:
    """两个编号都已知且不同才视为冲突。"""
    return label_a is not None and label_b is not None and label_a != label_b
