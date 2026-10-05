"""
直接量測原圖文字顏色（自動文字顏色用）

48px OCR 的顏色預測要再跑一次完整的 OCR 束搜尋，在 CPU 上很慢，結果也常偏灰。
這裡改成看像素：
1. 文字區域 = 該氣泡所有文字行多邊形；背景 = 文字區域外圍一圈的中位數顏色。
2. 文字區域內與背景差距夠大的像素視為筆畫，取「筆畫正中央」（離筆畫邊緣最遠）像素的中位數：
   彩色字加白邊時，白邊在外緣、字色在中央，不會誤判成白色；也避開抗鋸齒邊緣。
3. 接近純黑／純白的結果直接定為 #000000／#FFFFFF。

外框字（例如粉紅字＋白色外框＋外光暈，放在深色畫面上）時，文字外圍那一圈多半是外框或光暈，
會被誤當成背景，結果反而把字縫間的深色畫面當成字色。所以先用「由外往內的色層」判斷：
把區域分成幾種顏色、切成連通塊，從裁切邊緣（畫面）往內數要跨過幾層顏色，
最內層而且面積夠大的那種顏色就是字色（畫面 → 光暈 → 外框 → 字）。
抗鋸齒的細邊不算一層；和畫面同色的內層（字裡的洞：口、回、あ）不會被當成字色。
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


def _stroke_center_color(crop, inside, background, threshold):
    """取筆畫正中央的顏色。

    彩色字常加白色（或黑色）描邊：描邊在每個字的外緣，字本身的顏色在筆畫中央。
    以距離轉換找出離筆畫邊緣最遠的像素，避免把描邊誤認成文字顏色。
    """
    distance = np.linalg.norm(crop - background, axis=2)
    ink = ((distance >= threshold) & (inside > 0)).astype(np.uint8)
    if int(ink.sum()) < _MIN_STROKE_PIXELS:
        return None
    depth = cv2.distanceTransform(ink, cv2.DIST_L2, 3)
    values = depth[ink > 0]
    center = (ink > 0) & (depth >= max(1.0, float(np.percentile(values, 80))))
    if int(center.sum()) < 4:
        return None
    return np.median(crop[center], axis=0)


_LAYER_CLUSTERS = 4


def _layered_text_color(crop: np.ndarray, inside: np.ndarray) -> np.ndarray | None:
    """Colour of the innermost significant colour layer (see module docstring)."""
    height, width = crop.shape[:2]
    if height < 8 or width < 8:
        return None
    pixels = crop.reshape(-1, 3).astype(np.float32)
    # 分群只用抽樣的像素（大氣泡也夠快），再把每個像素指派到最近的顏色
    sample = pixels
    if len(pixels) > 20000:
        sample = pixels[np.random.default_rng(0).choice(len(pixels), 20000, replace=False)]
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    cv2.setRNGSeed(0)
    try:
        _, _, centers = cv2.kmeans(
            sample, _LAYER_CLUSTERS, None, criteria, 2, cv2.KMEANS_PP_CENTERS
        )
    except cv2.error:
        return None
    distances = ((pixels[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    labels = distances.argmin(axis=1).astype(np.int32).reshape(height, width)

    # 每種顏色各自切連通塊，合成一張全域編號圖（向量化，網點很多時也夠快）
    component = np.zeros((height, width), dtype=np.int32)
    cluster_parts: list[np.ndarray] = [np.array([-1])]
    thin_parts: list[np.ndarray] = [np.array([True])]
    size_parts: list[np.ndarray] = [np.array([0])]
    next_id = 1
    for cluster in range(_LAYER_CLUSTERS):
        mask = (labels == cluster).astype(np.uint8)
        if not mask.any():
            continue
        count, comp, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
        if count <= 1:
            continue
        depth_map = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
        max_depth = np.zeros(count, dtype=np.float32)
        np.maximum.at(max_depth, comp.ravel(), depth_map.ravel())
        local_sizes = stats[1:, cv2.CC_STAT_AREA]
        selected = mask > 0
        component[selected] = comp[selected] + (next_id - 1)
        cluster_parts.append(np.full(count - 1, cluster))
        size_parts.append(local_sizes)
        # 抗鋸齒細邊、網點：太細或太小，不算一層
        thin_parts.append((max_depth[1:] < 1.5) | (local_sizes < 6))
        next_id += count - 1
    total = next_id
    cluster_array = np.concatenate(cluster_parts)
    thin_array = np.concatenate(thin_parts)
    size_array = np.concatenate(size_parts)
    cluster_of = cluster_array.tolist()
    thin = thin_array.tolist()
    sizes = size_array.tolist()

    # 相鄰關係
    edges = []
    for a, b in (
        (component[:, :-1], component[:, 1:]),
        (component[:-1, :], component[1:, :]),
    ):
        diff = a != b
        edges.append(np.stack([a[diff], b[diff]], axis=1))
    pairs = np.concatenate(edges).astype(np.int64)
    keys = np.unique(np.concatenate([pairs[:, 0] * total + pairs[:, 1], pairs[:, 1] * total + pairs[:, 0]]))
    neighbours: list[list[int]] = [[] for _ in range(total)]
    for x, y in zip((keys // total).tolist(), (keys % total).tolist()):
        neighbours[x].append(y)

    # 0-1 BFS：從碰到裁切邊緣的色塊（畫面）開始，往內每跨過一個「夠厚」的色塊加一層
    from collections import deque

    inf = 1 << 30
    depth = [inf] * total
    queue: deque[int] = deque()
    frame = np.concatenate(
        [component[0, :], component[-1, :], component[:, 0], component[:, -1]]
    )
    for start in set(frame.tolist()):
        depth[start] = 0
        queue.append(start)
    while queue:
        node = queue.popleft()
        for other in neighbours[node]:
            step = 0 if thin[other] else 1
            candidate = depth[node] + step
            if candidate < depth[other]:
                depth[other] = candidate
                if step == 0:
                    queue.appendleft(other)
                else:
                    queue.append(other)

    inside_mask = inside > 0
    in_text = np.bincount(component[inside_mask].ravel(), minlength=total)
    # 佔裁切邊緣夠多的顏色才算畫面（背景）；裁得很緊時外框、字也會碰到邊緣
    frame_labels = np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
    frame_share = np.bincount(frame_labels, minlength=_LAYER_CLUSTERS) / max(1, frame_labels.size)
    background_clusters = {c for c in range(_LAYER_CLUSTERS) if frame_share[c] >= 0.25}
    # 每種顏色在「畫面以內」的面積與平均深度
    area: dict[int, int] = {}
    weighted: dict[int, float] = {}
    for node in range(1, total):
        if thin[node] or depth[node] in (0, inf) or in_text[node] < 0.5 * sizes[node]:
            continue
        cluster = cluster_of[node]
        area[cluster] = area.get(cluster, 0) + sizes[node]
        weighted[cluster] = weighted.get(cluster, 0.0) + sizes[node] * depth[node]
    if not area:
        return None
    significant = sum(area.values())
    minimum = max(30, 0.08 * significant)
    candidates = [
        (weighted[cluster] / cluster_area, cluster_area, cluster)
        for cluster, cluster_area in area.items()
        if cluster_area >= minimum
    ]
    # 和畫面同色的內層幾乎都是字裡的洞（口、回、あ），不當字色。
    # 代價：「黑字＋白框放在全黑畫面上」會量成白字（配黑框），仍然看得清楚。
    preferred = [item for item in candidates if item[2] not in background_clusters]
    if not preferred:
        return None
    _, _, cluster = max(preferred)
    depth_array = np.asarray(depth)
    keep = (cluster_array == cluster) & ~thin_array & (depth_array != 0) & (depth_array != inf)
    region = keep[component].astype(np.uint8)
    # 取那一層正中央的像素，避開邊緣混色
    center_depth = cv2.distanceTransform(region, cv2.DIST_L2, 3)
    values = center_depth[region > 0]
    core = (region > 0) & (center_depth >= max(1.0, float(np.percentile(values, 60))))
    if int(core.sum()) < 4:
        core = region > 0
    return np.median(crop[core], axis=0)


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
    foreground = _layered_text_color(crop, inside)
    if foreground is None:
        foreground = _stroke_center_color(crop, inside, background, threshold)
    if foreground is None:
        stroke_distance = distance[strokes]
        core = text_pixels[strokes][stroke_distance >= np.percentile(stroke_distance, 60)]
        foreground = np.median(core, axis=0)
    confidence = float(min(1.0, np.linalg.norm(foreground - background) / 220.0))
    return {
        "fg_color": _snap(foreground),
        "bg_color": _snap(background),
        "confidence": round(confidence, 4),
    }


def contrast_stroke_color(foreground) -> str:
    """自動顏色時的描邊色：白／淺色字用黑邊，其他用白邊，譯文在畫面上才看得清楚。"""
    r, g, b = (int(v) for v in foreground)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luminance >= 170 else "#FFFFFF"


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
