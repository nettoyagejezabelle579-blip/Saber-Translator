"""去字遮罩要連字的白框、光暈一起蓋住（使用者回報：灰色畫面上留下白色殘影）。"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from src.core import inpainting

FONT = "src/backend_v2/resources/fonts/思源黑体SourceHanSansK-Bold.TTF"
TEXT = "就是說又被像剛才那樣注入了魔力"


def _gradient(w: int, h: int) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    base = np.stack([150 + 30 * yy / h, 155 + 25 * yy / h, 175 + 20 * xx / w], axis=2)
    for k in range(5):  # 斜向亮紋
        base[np.abs((xx + yy * 0.6) - (60 + k * 90)) < 6] += 25
    return np.clip(base, 0, 255).astype(np.uint8)


def _positions():
    return [(150 - c * 70, 20 + r * 72, ch) for c, col in enumerate((TEXT[:8], TEXT[8:])) for r, ch in enumerate(col)]


def _outlined_scene():
    bg = _gradient(260, 620)
    img = Image.fromarray(bg)
    font = ImageFont.truetype(FONT, 46)
    halo = Image.new("L", img.size, 0)
    hd = ImageDraw.Draw(halo)
    for x, y, ch in _positions():
        hd.text((x, y), ch, font=font, fill=255, stroke_width=13, stroke_fill=255)
    halo = halo.filter(ImageFilter.GaussianBlur(5)).point(lambda v: int(v * 0.8))
    img.paste(Image.new("RGB", img.size, (245, 245, 250)), mask=halo)
    draw = ImageDraw.Draw(img)
    strokes = Image.new("L", img.size, 0)
    sd = ImageDraw.Draw(strokes)
    for x, y, ch in _positions():
        draw.text((x, y), ch, font=font, fill=(10, 10, 10), stroke_width=6, stroke_fill=(255, 255, 255))
        sd.text((x, y), ch, font=font, fill=255)
    draw.line([(10, 600), (250, 590)], fill=(40, 40, 60), width=3)  # 不相連的畫面線條
    return np.asarray(img), bg, np.asarray(strokes) > 127, (70, 10, 210, 600)


def _base_mask(strokes: np.ndarray) -> np.ndarray:
    return cv2.dilate(strokes.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0


def test_outline_and_glow_are_removed_but_separate_art_stays() -> None:
    img, true_bg, strokes, box = _outlined_scene()
    old = _base_mask(strokes)
    new = inpainting._outline_aware_mask(img, old, [box])

    def leftover(mask: np.ndarray) -> int:
        filled = cv2.inpaint(img, mask.astype(np.uint8) * 255, 7, cv2.INPAINT_TELEA)
        diff = np.abs(filled.astype(int) - true_bg.astype(int)).max(axis=2)
        x1, y1, x2, y2 = box
        return int((diff[y1:y2, x1:x2] > 35).sum())

    before, after = leftover(old), leftover(new)
    assert after < 0.05 * before, (before, after)  # 白框／光暈殘影幾乎全部消失
    art = np.zeros(strokes.shape, np.uint8)
    cv2.line(art, (10, 600), (250, 590), 1, 3)
    assert not (new & (art > 0)).any()  # 畫面線條不會被去掉


def test_plain_bubble_mask_stays_inside_the_bubble() -> None:
    image = Image.new("RGB", (300, 420), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 20, 280, 400), outline=(0, 0, 0), width=4)
    strokes = Image.new("L", image.size, 0)
    sd = ImageDraw.Draw(strokes)
    font = ImageFont.truetype(FONT, 40)
    for r, ch in enumerate("ちがうよ"):
        draw.text((130, 80 + r * 60), ch, font=font, fill=(0, 0, 0))
        sd.text((130, 80 + r * 60), ch, font=font, fill=255)
    img = np.asarray(image)
    old = _base_mask(np.asarray(strokes) > 127)
    new = inpainting._outline_aware_mask(img, old, [(110, 70, 190, 330)])
    border = np.zeros(old.shape, np.uint8)
    cv2.ellipse(border, (150, 210), (130, 190), 0, 0, 360, 1, 6)
    assert not (new & (border > 0)).any()
    # 白底黑字沒有外框：只多出抗鋸齒邊，不會大幅擴張
    assert new.sum() <= old.sum() * 1.6


def test_text_on_screentone_does_not_swallow_the_page() -> None:
    image = Image.new("RGB", (300, 420), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, 420, 6):
        for x in range(0, 300, 6):
            draw.ellipse((x, y, x + 2, y + 2), fill=(90, 90, 90))
    strokes = Image.new("L", image.size, 0)
    sd = ImageDraw.Draw(strokes)
    font = ImageFont.truetype(FONT, 40)
    for r, ch in enumerate("ちがう"):
        draw.text((130, 80 + r * 60), ch, font=font, fill=(0, 0, 0), stroke_width=4, stroke_fill=(255, 255, 255))
        sd.text((130, 80 + r * 60), ch, font=font, fill=255)
    img = np.asarray(image)
    old = _base_mask(np.asarray(strokes) > 127)
    new = inpainting._outline_aware_mask(img, old, [(110, 70, 190, 270)])
    # 白框被納入，但不會沿著網點一路擴散到整頁
    assert new.sum() > old.sum()
    assert not new[:, :60].any() and not new[:, 250:].any() and not new[330:, :].any()
