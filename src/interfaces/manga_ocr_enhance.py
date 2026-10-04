"""MangaOCR accuracy helpers: score each reading and retry hard crops.

MangaOCR reads a crop greedily once. Stylised fonts, screentone backgrounds,
outlined or white text and thin kanji strokes often give a wrong character
with low model confidence. Here every reading gets a score (mean log
probability of its tokens); when the first reading is not confident, the crop
is read again from cleaned-up views (margin, contrast, binarised, denoised,
inverted) and with beam search, and the most confident reading wins.

Everything works on a ``manga_ocr.MangaOcr``-like object (``processor``,
``tokenizer``, ``model``) so it can be tested without the real model.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger("MangaOCREnhance")


@dataclass(frozen=True)
class Reading:
    text: str
    score: float  # mean token log probability, higher is better (0 = certain)
    view: str
    beams: int


def _post_process(text: str) -> str:
    try:
        from manga_ocr.ocr import post_process
    except ImportError:  # 測試環境沒有 manga_ocr
        return "".join(text.split())
    return post_process(text)


def read_scored(ocr, image: Image.Image, *, view: str = "orig", num_beams: int = 1) -> Reading:
    """One MangaOCR reading with its confidence."""
    import torch

    rgb = image.convert("L").convert("RGB")
    pixels = ocr.processor(rgb, return_tensors="pt").pixel_values.to(ocr.model.device)
    with torch.inference_mode():
        output = ocr.model.generate(
            pixels,
            max_length=300,
            num_beams=num_beams,
            output_scores=True,
            return_dict_in_generate=True,
        )
    sequence = output.sequences[0]
    text = _post_process(ocr.tokenizer.decode(sequence, skip_special_tokens=True))
    score = -math.inf
    try:
        transition = ocr.model.compute_transition_scores(
            output.sequences,
            output.scores,
            getattr(output, "beam_indices", None) if num_beams > 1 else None,
            normalize_logits=num_beams == 1,
        )[0]
        values = transition[torch.isfinite(transition)]
        if values.numel():
            score = float(values.mean())
    except Exception:  # 舊版 transformers：沒有分數就只當作一般讀取
        logger.debug("MangaOCR 無法取得信心分數", exc_info=True)
    return Reading(text=text, score=score, view=view, beams=num_beams)


def _border_color(gray: np.ndarray) -> int:
    edge = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
    return int(np.median(edge)) if edge.size else 255


def _pad(gray: Image.Image, ratio: float = 0.08) -> Image.Image:
    array = np.asarray(gray)
    margin = max(6, round(ratio * min(gray.size)))
    return ImageOps.expand(gray, border=margin, fill=_border_color(array))


def _dark_text_on_light(gray: Image.Image) -> Image.Image:
    """Make the text dark: invert when the background (border) is dark."""
    if _border_color(np.asarray(gray)) < 110:
        return ImageOps.invert(gray)
    return gray


def _binarise(gray: Image.Image) -> Image.Image:
    array = np.asarray(gray, dtype=np.uint8)
    histogram = np.bincount(array.ravel(), minlength=256).astype(np.float64)
    total = array.size
    cumulative = np.cumsum(histogram)
    cumulative_mean = np.cumsum(histogram * np.arange(256))
    global_mean = cumulative_mean[-1] / max(total, 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        between = (global_mean * cumulative - cumulative_mean) ** 2 / (cumulative * (total - cumulative))
    threshold = int(np.nanargmax(between)) if np.isfinite(between).any() else 128
    binary = np.where(array > threshold, 255, 0).astype(np.uint8)
    return Image.fromarray(binary)


def _squarer(gray: Image.Image, max_aspect: float = 2.0) -> Image.Image:
    """Pad a long strip towards a square so the model's 224x224 resize distorts it less."""
    width, height = gray.size
    fill = _border_color(np.asarray(gray))
    if width > height * max_aspect:
        target = (width, round(width / max_aspect))
    elif height > width * max_aspect:
        target = (round(height / max_aspect), height)
    else:
        return _pad(gray)
    canvas = Image.new("L", target, fill)
    canvas.paste(gray, ((target[0] - width) // 2, (target[1] - height) // 2))
    return canvas


def candidate_views(image: Image.Image) -> list[tuple[str, Image.Image]]:
    """Cleaned-up versions of a crop for a second reading (the original is read first)."""
    gray = _dark_text_on_light(image.convert("L"))
    views = [
        ("pad", _pad(gray)),
        ("contrast", _pad(ImageOps.autocontrast(gray, cutoff=2))),
        ("binary", _pad(_binarise(gray.filter(ImageFilter.MedianFilter(3))))),
        ("square", _squarer(gray)),
        # 空心字、細筆畫：加粗後比較像一般實心字
        ("bold", _pad(gray.filter(ImageFilter.MinFilter(3)))),
    ]
    if min(gray.size) < 48:
        scale = 64 / max(min(gray.size), 1)
        size = (max(1, round(gray.width * scale)), max(1, round(gray.height * scale)))
        views.append(("upscale", _pad(gray.resize(size, Image.LANCZOS))))
    return views


# 依合成漫畫字評測（13 種字型、5 種情況、468 句）選出：只加入這三種重讀圖，
# 字元錯誤率 2.2% → 1.73%；加粗／留白／beam search 會產生「很有把握但錯」的結果，反而變差。
DEFAULT_RETRY_VIEWS = ("contrast", "binary", "square")


def best_reading(
    ocr,
    image: Image.Image,
    *,
    confident_score: float = -0.05,
    views: tuple[str, ...] = DEFAULT_RETRY_VIEWS,
    beams: int = 0,
) -> Reading:
    """Read once; if not confident, re-read the chosen cleaned views and keep the most confident."""
    first = read_scored(ocr, image)
    if first.score >= confident_score or not first.text:
        return first
    readings = [first]
    for name, view in candidate_views(image):
        try:
            if name in views:
                readings.append(read_scored(ocr, view, view=name))
        finally:
            view.close()
    best = max(readings, key=lambda reading: reading.score)
    if best.score < confident_score and beams > 1:
        source = image if best.view == "orig" else dict(candidate_views(image)).get(best.view, image)
        beam = read_scored(ocr, source, view=best.view, num_beams=beams)
        if beam.score > best.score:
            best = beam
    if best is not first:
        logger.debug(
            "MangaOCR 重讀：%r (%.3f) -> %r (%.3f, %s, beams=%d)",
            first.text, first.score, best.text, best.score, best.view, best.beams,
        )
    return best
