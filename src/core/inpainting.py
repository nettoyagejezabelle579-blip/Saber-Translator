import logging
import math
import numpy as np
from PIL import Image, ImageDraw
import cv2 # 需要 cv2 来创建掩码

from src.interfaces.lama_interface import clean_image_with_lama

from src.shared import constants

logger = logging.getLogger("CoreInpainting")


def _validate_bubble_geometry(bubble_coords, bubble_polygons=None):
    if not isinstance(bubble_coords, list):
        raise ValueError("气泡坐标必须是数组")
    if bubble_polygons is not None and not isinstance(bubble_polygons, list):
        raise ValueError("气泡多边形必须是数组")
    if bubble_polygons is not None and len(bubble_polygons) != len(bubble_coords):
        raise ValueError("气泡多边形数量与坐标数量不匹配")
    for index, coords in enumerate(bubble_coords):
        if (
            not isinstance(coords, (list, tuple))
            or len(coords) != 4
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in coords
            )
        ):
            raise ValueError(f"气泡 {index} 坐标必须包含四个整数")
        x1, y1, x2, y2 = coords
        if x1 >= x2 or y1 >= y2:
            raise ValueError(f"气泡 {index} 坐标必须描述正面积区域")
        if bubble_polygons is None or not bubble_polygons[index]:
            continue
        polygon = bubble_polygons[index]
        if (
            not isinstance(polygon, list)
            or len(polygon) != 4
            or any(
                not isinstance(point, list)
                or len(point) != 2
                or any(
                    isinstance(value, bool) or not isinstance(value, int)
                    for value in point
                )
                for point in polygon
            )
        ):
            raise ValueError(f"气泡 {index} 多边形必须包含四个整数点")


def create_bubble_mask(image_size, bubble_coords, bubble_polygons=None):
    """创建黑色为修复区域的二值掩膜。

    Args:
        image_size: 图像尺寸 (height, width, channels) 或 (height, width)
        bubble_coords: 当前文本框坐标列表 [(x1, y1, x2, y2), ...]
        bubble_polygons: 可选，气泡多边形坐标列表 [[[x1,y1], [x2,y2], [x3,y3], [x4,y4]], ...]
                        如果提供，将使用多边形而不是矩形来创建掩码
    """
    logger.debug(f"创建气泡掩码: {len(bubble_coords)} 个")
    if len(image_size) < 2 or image_size[0] <= 0 or image_size[1] <= 0:
        raise ValueError("图像尺寸无效")
    if not bubble_coords:
        return np.ones(image_size[:2], dtype=np.uint8) * 255
    _validate_bubble_geometry(bubble_coords, bubble_polygons)

    # 创建全白掩码（全部保留）
    mask = np.ones(image_size[:2], dtype=np.uint8) * 255
    
    for i, coords in enumerate(bubble_coords):
        x1, y1, x2, y2 = coords
        # 有解析后的当前多边形时，不再混入轴对齐边缘。
        if bubble_polygons is not None:
            polygon = bubble_polygons[i]
            if polygon:
                pts = np.array(polygon, dtype=np.int32)
                cv2.fillPoly(mask, [pts], 0)
            else:
                cv2.rectangle(mask, (x1, y1), (x2, y2), 0, -1)
        else:
            cv2.rectangle(mask, (x1, y1), (x2, y2), 0, -1)

    return mask

# ========== 智能纯色填充 ==========

# 背景像素颜色标准差低于此值视为纯色气泡底
_UNIFORM_BG_STD = 20.0
# 采样到的气泡底色与用户填充色的 RGB 距离不超过此值时，用采样色替代
# （例如扫描件的米黄/灰白气泡用 #FFFFFF 填充会留下明显色块）
_SAMPLE_COLOR_MAX_DISTANCE = 60.0
_MIN_BG_SAMPLES = 20


def _bubble_region_mask(shape, coords, polygon):
    region = np.zeros(shape[:2], dtype=np.uint8)
    if polygon:
        cv2.fillPoly(region, [np.asarray(polygon, dtype=np.int32)], 1)
    else:
        x1, y1, x2, y2 = coords
        cv2.rectangle(region, (x1, y1), (x2, y2), 1, -1)
    return region.astype(bool)


def _outline_aware_mask(image_rgb, repair_mask, bubble_coords):
    """把文字的外框、光暈、抗鋸齒邊一起納入去字遮罩。

    精確文字遮罩只蓋住字的筆畫；彩色畫面上的字常有粗白框和柔和的光暈，固定膨脹
    幾個像素蓋不完，修復後就留下白色殘影。這裡在每個文字框附近：
    1. 用「離字夠遠」的像素做大範圍加權模糊，估計逐像素的背景色（漸層畫面也適用）；
    2. 離字 R 像素以內、和背景色明顯不同的像素視為外框／光暈；
    3. 只保留和文字筆畫相連的那些（不會吃掉旁邊不相連的畫面線條）。
    R 依筆畫粗細而定，並有上限，不會擴到遠處的畫面。回傳新的 bool 遮罩。
    """
    height, width = repair_mask.shape
    expanded = repair_mask.copy()
    page_scale = max(height, width)
    for x1, y1, x2, y2 in bubble_coords:
        box_w, box_h = x2 - x1, y2 - y1
        if box_w <= 2 or box_h <= 2:
            continue
        limit = max(8, round(page_scale / 25))
        cx1, cy1 = max(0, x1 - 3 * limit), max(0, y1 - 3 * limit)
        cx2, cy2 = min(width, x2 + 3 * limit), min(height, y2 + 3 * limit)
        text = repair_mask[cy1:cy2, cx1:cx2]
        if not text.any():
            continue
        crop = image_rgb[cy1:cy2, cx1:cx2].astype(np.float32)
        # 筆畫粗細：遮罩內距離轉換的高百分位約為半個筆畫寬
        inside = cv2.distanceTransform(text.astype(np.uint8), cv2.DIST_L2, 3)
        stroke = max(1.0, float(np.percentile(inside[text], 90)) * 2.0)
        # 外框加光暈通常不超過幾個筆畫寬；上限避免擴到遠處的畫面
        radius = int(min(limit, max(8.0, 4.0 * stroke + 6)))
        distance = cv2.distanceTransform((~text).astype(np.uint8), cv2.DIST_L2, 3)
        far = (distance > radius + 1).astype(np.float32)
        if far.sum() < 50:
            continue
        # 局部平均色與局部起伏（紋理）：網點畫面上，白框是「沒有網點的平滑區」，
        # 只看單一像素顏色分不出白框和網點間的白紙
        window = max(5, round(page_scale / 220)) | 1
        local_mean = cv2.blur(crop, (window, window))
        local_sq = cv2.blur(crop * crop, (window, window))
        local_std = np.sqrt(np.maximum(local_sq - local_mean * local_mean, 0.0)).mean(axis=2)
        # 逐像素背景：只用遠處像素做加權模糊（normalized convolution），漸層畫面也適用
        sigma = max(4.0, 1.5 * radius)
        weight = cv2.GaussianBlur(far, (0, 0), sigma)
        safe_weight = np.maximum(weight, 1e-3)
        background = np.stack(
            [cv2.GaussianBlur(local_mean[:, :, c] * far, (0, 0), sigma) for c in range(3)], axis=2
        ) / safe_weight[:, :, None]
        background_std = cv2.GaussianBlur(local_std * far, (0, 0), sigma) / safe_weight
        valid = weight > 0.02
        difference = np.abs(local_mean - background).max(axis=2)
        far_valid = (far > 0) & valid
        noise = float(np.percentile(difference[far_valid], 90)) if far_valid.any() else 0.0
        threshold = max(18.0, noise + 12.0)
        textured = background_std > 12.0
        smooth_patch = textured & (local_std < 0.4 * background_std)
        candidate = (distance <= radius) & valid & ((difference > threshold) | smooth_patch)
        joined = (candidate | text).astype(np.uint8)
        count, labels = cv2.connectedComponents(joined, connectivity=8)
        if count <= 1:
            continue
        attached = np.unique(labels[text])
        grow = np.isin(labels, attached[attached > 0]) & candidate
        if grow.any():
            # 光暈邊緣再補 1px，避免留下一圈淡淡的亮邊
            grow = cv2.dilate(grow.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
            expanded[cy1:cy2, cx1:cx2] |= grow & (distance <= radius + 1)
    return expanded


def _residue_mask(result, repaired_mask):
    """找出去字後黏在修復區外緣的殘留（白邊、彩色描邊、抗鋸齒灰邊）。

    做法：修復區外圍一圈（band）裡、和更外圍背景（outer）明顯不同的像素視為殘留；
    但只保留完全落在 band 內、並貼著修復區的色塊——氣泡外框、畫面線條會延伸到
    outer，不會被誤刪。回傳 bool 遮罩；沒有殘留時回傳 None。
    """
    height, width = repaired_mask.shape
    band = max(4, round(max(height, width) / 250))
    mask_u8 = repaired_mask.astype(np.uint8)
    near = cv2.dilate(mask_u8, cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1))) > 0
    far = cv2.dilate(mask_u8, cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (6 * band + 1, 6 * band + 1))) > 0
    touching = cv2.dilate(mask_u8, np.ones((3, 3), np.uint8)) > 0
    ring = near & ~repaired_mask
    outer = far & ~near
    count, labels, stats, _ = cv2.connectedComponentsWithStats(far.astype(np.uint8), 8)
    residue = np.zeros_like(repaired_mask)
    for label in range(1, count):
        x, y, w, h, _area = stats[label]
        region = labels[y:y + h, x:x + w] == label
        crop = result[y:y + h, x:x + w].astype(np.int16)
        crop_outer = outer[y:y + h, x:x + w] & region
        crop_ring = ring[y:y + h, x:x + w] & region
        if crop_outer.sum() < 30 or not crop_ring.any():
            continue
        reference = np.median(crop[crop_outer], axis=0)
        distance = np.abs(crop - reference).max(axis=2)
        threshold = max(40.0, float(np.percentile(distance[crop_outer], 95)) + 25.0)
        outlier = ((distance > threshold) & (crop_ring | crop_outer)).astype(np.uint8)
        blobs, blob_labels = cv2.connectedComponents(outlier, connectivity=8)
        if blobs <= 1:
            continue
        reaches_outer = set(np.unique(blob_labels[crop_outer & (outlier > 0)]).tolist())
        hugs_text = set(np.unique(blob_labels[touching[y:y + h, x:x + w] & (outlier > 0)]).tolist())
        keep = [b for b in range(1, blobs) if b in hugs_text and b not in reaches_outer]
        if keep:
            residue[y:y + h, x:x + w] |= np.isin(blob_labels, keep)
    if not residue.any():
        return None
    residue = cv2.dilate(residue.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    return residue & ~repaired_mask & near


def _despeckle_flat_regions(result_img, repaired_mask):
    """去字後殘留的小點清除。

    只處理周圍是純色的區域（白色或淺色氣泡）：在修復區及外圍一圈內，
    與底色差異明顯的小連通塊（灰點、彩色點、白點）直接填成底色。
    畫面、網點等有紋理的區域不動。回傳新圖；沒有需要清理的地方時回傳 None。
    """
    if not repaired_mask.any():
        return None
    result = np.array(result_img.convert("RGB"))
    height, width = repaired_mask.shape
    band = max(4, round(max(height, width) / 300))
    near = cv2.dilate(
        repaired_mask.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1)),
    ) > 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats(near.astype(np.uint8), 8)
    changed = False
    for label in range(1, count):
        x, y, w, h, _area = stats[label]
        region = labels[y:y + h, x:x + w] == label
        crop = result[y:y + h, x:x + w]
        pixels = crop[region].astype(np.int16)
        if len(pixels) < 50:
            continue
        background = np.median(pixels, axis=0)
        distance = np.abs(pixels - background).max(axis=1)
        # 至少 80% 像素接近底色才算純色區域（殘點多時也能清）
        if float((distance <= 24).mean()) < 0.8:
            continue
        outlier = np.zeros(region.shape, np.uint8)
        outlier[region] = (distance > 24).astype(np.uint8)
        dots, dot_labels, dot_stats, _ = cv2.connectedComponentsWithStats(outlier, 8)
        max_dot = max(40, int(0.002 * region.sum()))
        # 碰到範圍邊緣的色塊（例如延伸進來的氣泡外框）不是殘點
        padded = np.pad(region.astype(np.uint8), 1)
        edge = region & (cv2.erode(padded, np.ones((3, 3), np.uint8))[1:-1, 1:-1] == 0)
        edge_dots = set(np.unique(dot_labels[edge]).tolist())
        speck = np.zeros(region.shape, bool)
        for dot in range(1, dots):
            # 大塊（氣泡外框、刻意保留的圖案）不動，只清小點
            if dot not in edge_dots and dot_stats[dot, cv2.CC_STAT_AREA] <= max_dot:
                speck |= dot_labels == dot
        if speck.any():
            speck = cv2.dilate(speck.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
            speck &= region
            crop[speck] = background.astype(np.uint8)
            changed = True
    return Image.fromarray(result) if changed else None


def _pick_fill_color(samples, configured):
    """在采样底色和用户填充色之间选择。"""
    if samples.shape[0] < _MIN_BG_SAMPLES:
        return np.asarray(configured, dtype=np.uint8), True
    median = np.median(samples, axis=0)
    uniform = float(samples.std(axis=0).max()) <= _UNIFORM_BG_STD
    distance = float(np.linalg.norm(median - np.asarray(configured, dtype=np.float32)))
    if distance <= _SAMPLE_COLOR_MAX_DISTANCE:
        return np.clip(np.rint(median), 0, 255).astype(np.uint8), uniform
    return np.asarray(configured, dtype=np.uint8), uniform


def _smart_solid_fill(result_np, fill_mask, bubble_coords, bubble_polygons, configured):
    """
    逐气泡的纯色填充：
    - 纯色底的气泡：用采样到的气泡底色填充，并向外多覆盖 1px 抗锯齿边缘，去掉文字残影；
    - 有纹理/渐变底（图上文字）：用 OpenCV Telea 局部修复代替一整块纯色，CPU 开销很小；
    - 气泡之外的用户笔刷区域：保持使用配置的填充色。
    """
    h, w = fill_mask.shape
    handled = np.zeros_like(fill_mask)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    pad = 8
    for index, coords in enumerate(bubble_coords):
        polygon = bubble_polygons[index] if bubble_polygons is not None else None
        x1, y1, x2, y2 = coords
        if polygon:
            pts = np.asarray(polygon)
            x1, y1 = int(pts[:, 0].min()), int(pts[:, 1].min())
            x2, y2 = int(pts[:, 0].max()), int(pts[:, 1].max())
        cx1, cy1 = max(0, x1 - pad), max(0, y1 - pad)
        cx2, cy2 = min(w, x2 + pad + 1), min(h, y2 + pad + 1)
        if cx2 <= cx1 or cy2 <= cy1:
            continue

        region = _bubble_region_mask((h, w), coords, polygon)[cy1:cy2, cx1:cx2]
        crop_fill = fill_mask[cy1:cy2, cx1:cx2] & ~handled[cy1:cy2, cx1:cx2]
        selected = crop_fill & region
        if not selected.any():
            continue

        crop = result_np[cy1:cy2, cx1:cx2]
        grown = cv2.dilate(selected.astype(np.uint8), kernel, iterations=2).astype(bool)
        background = region & ~grown
        color, uniform = _pick_fill_color(crop[background].astype(np.float32), configured)

        if uniform:
            target = cv2.dilate(selected.astype(np.uint8), kernel, iterations=1).astype(bool)
            target &= region
            crop[target] = color
        else:
            inpaint_mask = cv2.dilate(selected.astype(np.uint8), kernel, iterations=1) * 255
            repaired = cv2.inpaint(crop, inpaint_mask, 3, cv2.INPAINT_TELEA)
            target = inpaint_mask.astype(bool) & region
            crop[target] = repaired[target]
        handled[cy1:cy2, cx1:cx2] |= selected

    remaining = fill_mask & ~handled
    if remaining.any():
        result_np[remaining] = configured
    return result_np


def _sampled_box_fill_color(image_pil, coords, polygon, fill_color):
    """整框填充（无精确掩膜）时，用框内像素中位数校正填充色。"""
    if not constants.SMART_SOLID_FILL:
        return fill_color
    configured = np.array(
        [int(fill_color[1:3], 16), int(fill_color[3:5], 16), int(fill_color[5:7], 16)],
        dtype=np.float32,
    )
    x1, y1, x2, y2 = coords
    if polygon:
        pts = np.asarray(polygon)
        x1, y1 = int(pts[:, 0].min()), int(pts[:, 1].min())
        x2, y2 = int(pts[:, 0].max()), int(pts[:, 1].max())
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(image_pil.width, x2), min(image_pil.height, y2)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return fill_color
    crop = image_pil.crop((x1, y1, x2, y2)).convert('RGB')
    try:
        samples = np.asarray(crop, dtype=np.float32).reshape(-1, 3)
    finally:
        crop.close()
    color, _ = _pick_fill_color(samples, configured)
    return '#%02x%02x%02x' % tuple(int(v) for v in color)


def inpaint_bubbles(image_pil, bubble_coords, method=constants.DEFAULT_INPAINT_METHOD, fill_color=None, bubble_polygons=None, precise_mask=None, user_mask=None, mask_dilate_size=0, mask_box_expand_ratio=0, lama_model='lama_mpe', disable_resize=False, regional_inpainting=False):
    """
    根据指定方法修复或填充图像中的气泡区域。

    Args:
        image_pil (PIL.Image.Image): 原始 PIL 图像。
        bubble_coords (list): 气泡坐标列表 [(x1, y1, x2, y2), ...]。
        method (str): 修复方法 ('solid', 'lama')。
        fill_color (str | None): 'solid' 方法使用的填充颜色；LaMA 不接受。
        bubble_polygons (list): 可选，气泡多边形坐标列表 [[[x1,y1], [x2,y2], [x3,y3], [x4,y4]], ...]
                               如果提供，将使用多边形而不是矩形来创建掩码和填充
        precise_mask (np.ndarray): 可选，模型生成的精确文字掩膜（textMask）。
                                   如果提供，将直接使用此掩膜而非根据坐标生成。
                                   仅 CTD/Default 检测器支持生成此掩膜。
        user_mask (np.ndarray): 可选，用户笔刷掩膜（userMask）。
                                白色(255)=用户标记需要修复的区域
                                黑色(0)=用户标记需要保留的区域
                                灰色(127)=未修改，使用自动检测结果
        mask_dilate_size (int): 掩膜膨胀大小（像素），用于扩大修复区域。
        mask_box_expand_ratio (int): 标注框区域扩大比例（%），用于扩大标注框的收录范围。
        lama_model (str): 'lama_mpe' (速度优化)、'litelama' (通用) 或 'lama_manga' (漫画)
        disable_resize (bool): 是否禁止 LaMA 自动缩放。
        regional_inpainting (bool): 是否按局部区域保留上下文并分别修复。

    Returns:
        PIL.Image.Image: 处理后的 PIL 图像。
    """
    if not isinstance(image_pil, Image.Image):
        raise ValueError("修复输入必须是 PIL 图像")
    if not isinstance(bubble_coords, list):
        raise ValueError("气泡坐标必须是数组")
    if not bubble_coords:
        logger.debug("无气泡坐标，跳过修复")
        return image_pil.copy()

    _validate_bubble_geometry(bubble_coords, bubble_polygons)

    if method not in {"solid", "lama"}:
        raise ValueError(f"不支持的修复方法: {method}")
    if method == "solid":
        if not isinstance(fill_color, str) or not (
            len(fill_color) == 7
            and fill_color.startswith("#")
            and all(
                character in "0123456789abcdefABCDEF"
                for character in fill_color[1:]
            )
        ):
            raise ValueError("填充颜色必须是 #RRGGBB")
    elif fill_color is not None:
        raise ValueError("LaMA 修复不接受填充颜色")
    if method == "lama" and lama_model not in {"lama_mpe", "litelama", "lama_manga"}:
        raise ValueError("LaMA 模型必须是 lama_mpe、litelama 或 lama_manga")
    if not isinstance(disable_resize, bool):
        raise ValueError("disable_resize 必须是布尔值")
    if not isinstance(regional_inpainting, bool):
        raise ValueError("regional_inpainting 必须是布尔值")
    if isinstance(mask_dilate_size, bool) or not isinstance(mask_dilate_size, int) or mask_dilate_size < 0:
        raise ValueError("mask_dilate_size 必须是非负整数")
    if (
        isinstance(mask_box_expand_ratio, bool)
        or not isinstance(mask_box_expand_ratio, (int, float))
        or not math.isfinite(float(mask_box_expand_ratio))
        or mask_box_expand_ratio < 0
    ):
        raise ValueError("mask_box_expand_ratio 必须是非负有限数字")

    converted_image = image_pil.convert('RGB')
    try:
        image_rgb = np.array(converted_image)
        image_size = image_rgb.shape
    finally:
        if converted_image is not image_pil:
            converted_image.close()

    # 1. 创建掩码 (黑色为修复区)
    if precise_mask is not None:
        # 使用模型生成的精确文字掩膜
        logger.debug("使用精确文字掩膜")
        
        if (
            not isinstance(precise_mask, np.ndarray)
            or precise_mask.ndim != 2
            or precise_mask.dtype != np.uint8
            or precise_mask.shape != tuple(image_size[:2])
        ):
            raise ValueError("精确文字掩膜必须是与原图同尺寸的 uint8 单通道数组")
        
        # 反转掩膜：文字区域（高值）变为需要修复的区域（低值）
        text_mask = 255 - precise_mask
        
        # 应用阈值，确保是二值掩膜
        _, text_mask = cv2.threshold(text_mask, 127, 255, cv2.THRESH_BINARY)
        
        # 只保留标注框内的文字掩膜（只修复框出来的区域）
        # 创建一个标注框区域的掩膜
        box_region_mask = np.ones_like(text_mask) * 255  # 白色表示保留
        expand_ratio = mask_box_expand_ratio / 100.0  # 转换为小数
        
        for index, (x1, y1, x2, y2) in enumerate(bubble_coords):
            polygon = (
                bubble_polygons[index]
                if bubble_polygons is not None and bubble_polygons[index]
                else [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
            )
            points = np.asarray(polygon, dtype=np.float32)
            if expand_ratio > 0:
                center = points.mean(axis=0)
                points = center + (points - center) * (1.0 + expand_ratio)
            cv2.fillPoly(
                box_region_mask,
                [np.rint(points).astype(np.int32)],
                0,
            )
        
        if mask_box_expand_ratio > 0:
            logger.debug(f"标注框扩大 {mask_box_expand_ratio}%")
        
        # 合并掩膜：只有在标注框内且是文字区域的才需要修复
        # text_mask: 黑色=文字区域（需修复），白色=非文字区域
        # box_region_mask: 黑色=标注框内，白色=标注框外
        # 结果：只有两者都是黑色时才需要修复
        bubble_mask_np = np.maximum(text_mask, box_region_mask)
        
        # 掩膜膨胀处理（问题2：膨胀系数）
        if mask_dilate_size > 0 and getattr(constants, "ADAPTIVE_MASK_DILATE", False):
            # 膨胀像素數隨頁面尺寸放大：高解析度頁面的抗鋸齒邊、描邊也能完整蓋住
            mask_dilate_size = max(
                mask_dilate_size,
                round(mask_dilate_size * max(image_size[:2]) / 1500),
            )
        if mask_dilate_size > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (mask_dilate_size * 2 + 1, mask_dilate_size * 2 + 1))
            # 膨胀需要修复的区域（黑色区域），所以先反转，膨胀，再反转
            inverted = 255 - bubble_mask_np
            dilated = cv2.dilate(inverted, kernel, iterations=1)
            bubble_mask_np = 255 - dilated
            logger.debug(f"掩膜膨胀: {mask_dilate_size}px")

        if getattr(constants, "OUTLINE_AWARE_MASK", False):
            # 字的白框、光暈、抗鋸齒邊一起去掉，修復後才不會留下白色殘影
            repair = bubble_mask_np < 128
            grown = _outline_aware_mask(image_rgb, repair, bubble_coords)
            added = int(grown.sum() - repair.sum())
            if added > 0:
                logger.debug("去字遮罩納入外框／光暈：%d px", added)
                bubble_mask_np = np.where(grown, 0, 255).astype(np.uint8)
        
    else:
        # 使用坐标/多边形生成掩膜
        bubble_mask_np = create_bubble_mask(image_size, bubble_coords, bubble_polygons)
    
    if method == 'lama' and regional_inpainting and precise_mask is not None:
        # Close tiny automatic-mask holes before applying user repair/protection strokes.
        radius = max(1, round(2 * min(image_size[:2]) / 1024))
        repair_mask = np.pad(255 - bubble_mask_np, radius)
        repair_mask = cv2.morphologyEx(
            repair_mask, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1, 2*radius+1)),
        )
        bubble_mask_np = 255 - repair_mask[radius:-radius, radius:-radius]

    # ✅ 2. 叠加用户掩膜（不受标注框限制）
    if user_mask is not None:
        logger.debug("叠加用户笔刷掩膜")
        if (
            not isinstance(user_mask, np.ndarray)
            or user_mask.ndim != 2
            or user_mask.dtype != np.uint8
            or user_mask.shape != tuple(image_size[:2])
        ):
            raise ValueError("用户掩膜必须是与原图同尺寸的 uint8 单通道数组")
        
        # 统计用于调试
        white_count = np.sum(user_mask > 200)
        black_count = np.sum(user_mask < 50)
        gray_count = np.sum((user_mask >= 50) & (user_mask <= 200))
        logger.debug(f"用户掩膜统计: 白色(修复)={white_count}px, 黑色(保留)={black_count}px, 灰色(未改)={gray_count}px")
        
        # 叠加逻辑：
        # - user_mask 白色(>200) → bubble_mask_np 设为黑色（强制修复，不受标注框限制）
        # - user_mask 黑色(<50) → bubble_mask_np 设为白色（强制保留，不受标注框限制）
        # - user_mask 灰色 → 保持 bubble_mask_np 原值
        
        # 用户标记需要修复的区域（白色）→ 强制设为黑色
        user_repair_mask = user_mask > 200
        bubble_mask_np[user_repair_mask] = 0
        
        # 用户标记需要保留的区域（黑色）→ 强制设为白色
        user_preserve_mask = user_mask < 50
        bubble_mask_np[user_preserve_mask] = 255
        
        # 统计最终掩膜
        final_repair_count = np.sum(bubble_mask_np < 128)
        logger.debug(f"最终掩膜修复区域: {final_repair_count}px ({final_repair_count * 100 / bubble_mask_np.size:.2f}%)")
    
    if not np.any(bubble_mask_np < 128):
        raise ValueError("修复掩膜为空")

    bubble_mask_pil = Image.fromarray(bubble_mask_np)
    result_img = None
    try:
        if method == 'lama':
            logger.debug(f"使用 LAMA 修复 (模型: {lama_model})")
            result_img = clean_image_with_lama(
                image_pil,
                bubble_mask_pil,
                lama_model=lama_model,
                disable_resize=disable_resize,
                regional_inpainting=regional_inpainting,
            )
            if not isinstance(result_img, Image.Image):
                raise RuntimeError("LaMA 修复未返回图像")
            if result_img.size != image_pil.size:
                raise RuntimeError("LaMA 修复结果尺寸与输入图像不一致")
            if getattr(constants, "REPAIR_RESIDUE_CLEANUP", False):
                residue = _residue_mask(np.array(result_img.convert("RGB")), bubble_mask_np < 128)
                if residue is not None:
                    # 第一次修復會把外緣的白邊顏色帶進字的位置；把殘留併入遮罩，
                    # 從原圖重新修復，讓填色取自真正的背景
                    logger.debug("去字殘留二次修復：%d px", int(residue.sum()))
                    expanded = np.where((bubble_mask_np < 128) | residue, 0, 255).astype(np.uint8)
                    residue_mask_pil = Image.fromarray(expanded)
                    try:
                        second = clean_image_with_lama(
                            image_pil,
                            residue_mask_pil,
                            lama_model=lama_model,
                            disable_resize=disable_resize,
                            regional_inpainting=regional_inpainting,
                        )
                    finally:
                        residue_mask_pil.close()
                    bubble_mask_np = expanded
                    if isinstance(second, Image.Image) and second.size == result_img.size:
                        result_img.close()
                        result_img = second
            if getattr(constants, "REPAIR_DESPECKLE", False):
                cleaned = _despeckle_flat_regions(result_img, bubble_mask_np < 128)
                if cleaned is not None:
                    result_img.close()
                    result_img = cleaned
            logger.debug("LAMA 修复成功")
        else:
            result_img = image_pil.copy()
            use_mask = precise_mask is not None or user_mask is not None
            logger.debug(f"纯色填充: {fill_color}")
            if use_mask:
                converted_result = result_img.convert('RGB')
                try:
                    result_np = np.array(converted_result)
                finally:
                    if converted_result is not result_img:
                        converted_result.close()

                r = int(fill_color[1:3], 16)
                g = int(fill_color[3:5], 16)
                b = int(fill_color[5:7], 16)

                fill_mask = bubble_mask_np < 128
                if constants.SMART_SOLID_FILL:
                    result_np = _smart_solid_fill(
                        result_np,
                        fill_mask,
                        bubble_coords,
                        bubble_polygons,
                        (r, g, b),
                    )
                else:
                    result_np[fill_mask] = [r, g, b]
                replacement = Image.fromarray(result_np)
                result_img.close()
                result_img = replacement
                logger.debug("精确掩膜填充完成")
            else:
                draw = ImageDraw.Draw(result_img)
                for i, (x1, y1, x2, y2) in enumerate(bubble_coords):
                    polygon = bubble_polygons[i] if bubble_polygons is not None else None
                    box_color = _sampled_box_fill_color(
                        image_pil, (x1, y1, x2, y2), polygon, fill_color
                    )
                    if polygon:
                        pts = [(p[0], p[1]) for p in polygon]
                        draw.polygon(pts, fill=box_color)
                        continue
                    draw.rectangle(((x1, y1), (x2, y2)), fill=box_color)
            logger.debug("纯色填充完成")

        return result_img
    except Exception:
        if isinstance(result_img, Image.Image):
            result_img.close()
        raise
    finally:
        bubble_mask_pil.close()
