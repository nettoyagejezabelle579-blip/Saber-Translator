"""Measure MangaOCR accuracy on synthetic manga text (baseline vs. enhanced).

Renders known Japanese dialogue (kanji, hiragana, katakana) in hard
manga-style fonts and conditions, reads every sample with plain MangaOCR and
with ``best_reading``, and prints character error rates.

Usage: eval_ocr.py FONT_DIR [--limit N] [--save-dir DIR]
"""

from __future__ import annotations

import argparse
import io
import random
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

FONTS = {
    "NotoSansJP": "notosansjp/NotoSansJP[wght].ttf",
    "NotoSerifJP": "notoserifjp/NotoSerifJP[wght].ttf",
    "YujiSyuku(brush)": "yujisyuku/YujiSyuku-Regular.ttf",
    "YujiBoku(brush)": "yujiboku/YujiBoku-Regular.ttf",
    "ZenKurenaido(hand)": "zenkurenaido/ZenKurenaido-Regular.ttf",
    "HachiMaruPop(round)": "hachimarupop/HachiMaruPop-Regular.ttf",
    "YuseiMagic(marker)": "yuseimagic/YuseiMagic-Regular.ttf",
    "DelaGothic(heavy)": "delagothicone/DelaGothicOne-Regular.ttf",
    "RampartOne(outline)": "rampartone/RampartOne-Regular.ttf",
    "ReggaeOne(display)": "reggaeone/ReggaeOne-Regular.ttf",
    "KaiseiDecol": "kaiseidecol/KaiseiDecol-Regular.ttf",
    "MochiyPop": "mochiypopone/MochiyPopOne-Regular.ttf",
    "DotGothic16(pixel)": "dotgothic16/DotGothic16-Regular.ttf",
}

LINES = [
    "本当に大丈夫なの？",
    "先輩の部屋に入るのは初めて",
    "誰にも言わないって約束して",
    "もう我慢できないよ",
    "そんなに見つめないで恥ずかしい",
    "今日は帰りたくない気分なの",
    "身体が熱くて頭が真っ白",
    "優しくしてくれるって信じてた",
    "勝手に触らないでください",
    "まさか本気で言ってるの？",
    "鍵を閉め忘れたかもしれない",
    "未来の約束なんて意味がない",
    "末っ子だから甘えん坊なんだ",
    "己の欲望に負けるなんて",
    "既に準備は整っている",
    "輸入品の香水をつけてきた",
    "質問に答えてくれないの？",
    "旅館の露天風呂で二人きり",
    "微妙な距離感がもどかしい",
    "壁の向こうに聞こえちゃう",
    "コンビニでアイス買ってきた",
    "スマホの電源切っておいて",
    "ベッドの上でゴロゴロしてる",
    "シャワー浴びてからにしよう",
    "ソファーに座って待ってて",
    "ドキドキが止まらないの",
    "ヌルヌルして気持ちいい",
    "ツンデレなんかじゃない",
    "メイド服着てみたかったの",
    "クラスのみんなには内緒だよ",
    "嫉妬してるの？可愛いね",
    "責任取ってもらうからね",
    "濡れちゃってるじゃないか",
    "敏感なところばっかり",
    "膝枕してあげようか",
    "憧れの先生と二人っきり",
]

VERTICAL_ROTATE = set("ー～…")
VERTICAL_MAP = {"、": "︑", "。": "︒", "「": "﹁", "」": "﹂", "？": "？", "！": "！"}
STYLES = ("plain", "small", "screentone", "outlined", "degraded")


def fetch_fonts(font_dir: Path) -> dict[str, Path]:
    font_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, relative in FONTS.items():
        target = font_dir / Path(relative).name
        if not target.exists():
            url = "https://raw.githubusercontent.com/google/fonts/main/ofl/" + urllib.parse.quote(relative)
            target.write_bytes(urllib.request.urlopen(url, timeout=120).read())
        paths[name] = target
    return paths


def _glyph(char: str, font: ImageFont.FreeTypeFont, size: int, rotate: bool) -> Image.Image:
    cell = Image.new("L", (size * 2, size * 2), 0)
    draw = ImageDraw.Draw(cell)
    draw.text((size, size), char, font=font, fill=255, anchor="mm")
    if rotate:
        cell = cell.rotate(-90)
    box = (size // 2, size // 2, size // 2 + size, size // 2 + size)
    return cell.crop(box)


def render(text: str, font_path: Path, size: int, vertical: bool) -> Image.Image:
    """White glyph mask (L) of the text, one column or one row."""
    font = ImageFont.truetype(str(font_path), size)
    chars = [VERTICAL_MAP.get(c, c) if vertical else c for c in text]
    step = int(size * 1.08)
    if vertical:
        # 長句像真正的對話框一樣分成兩列，由右至左
        columns = [chars] if len(chars) <= 10 else [chars[: (len(chars) + 1) // 2], chars[(len(chars) + 1) // 2:]]
        gap = int(size * 0.35)
        width = len(columns) * size + (len(columns) - 1) * gap
        mask = Image.new("L", (width, step * len(columns[0])), 0)
        for column_index, column in enumerate(columns):
            x = width - size - column_index * (size + gap)
            for index, char in enumerate(column):
                mask.paste(_glyph(char, font, size, char in VERTICAL_ROTATE), (x, index * step))
    else:
        mask = Image.new("L", (step * len(chars), size), 0)
        for index, char in enumerate(chars):
            mask.paste(_glyph(char, font, size, False), (index * step, 0))
    return mask


def _screentone(size: tuple[int, int], spacing: int, radius: int, value: int) -> Image.Image:
    tone = Image.new("L", size, 255)
    draw = ImageDraw.Draw(tone)
    for y in range(0, size[1], spacing):
        offset = spacing // 2 if (y // spacing) % 2 else 0
        for x in range(-spacing, size[0], spacing):
            draw.ellipse((x + offset - radius, y - radius, x + offset + radius, y + radius), fill=value)
    return tone


def compose(mask: Image.Image, style: str, rng: random.Random) -> Image.Image:
    margin = max(8, mask.width // 10, mask.height // 30)
    size = (mask.width + 2 * margin, mask.height + 2 * margin)
    placed = Image.new("L", size, 0)
    placed.paste(mask, (margin, margin))
    if style == "screentone":
        canvas = _screentone(size, 6, 1, 150)
        canvas.paste(0, mask=placed)
    elif style == "outlined":
        canvas = _screentone(size, 5, 2, 90)
        stroke = placed.filter(ImageFilter.MaxFilter(7))
        canvas.paste(0, mask=stroke)
        canvas.paste(255, mask=placed)
    else:
        canvas = Image.new("L", size, 255)
        canvas.paste(0, mask=placed)
    if style == "degraded":
        canvas = canvas.filter(ImageFilter.GaussianBlur(0.9))
        buffer = io.BytesIO()
        canvas.save(buffer, "JPEG", quality=35)
        canvas = Image.open(io.BytesIO(buffer.getvalue())).convert("L")
    return canvas


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return "".join(c for c in text if unicodedata.category(c)[0] in "LN")


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def is_kanji(char: str) -> bool:
    return "一" <= char <= "鿿"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("font_dir")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--save-dir")
    args = parser.parse_args()

    from manga_ocr import MangaOcr
    from src.interfaces.manga_ocr_enhance import best_reading, read_scored

    fonts = fetch_fonts(Path(args.font_dir))
    ocr = MangaOcr(force_cpu=True)
    rng = random.Random(7)
    samples = []
    for font_name, font_path in fonts.items():
        for index, line in enumerate(LINES):
            style = STYLES[(index + len(samples)) % len(STYLES)]
            vertical = index % 3 != 0
            size = 18 if style == "small" else rng.choice((28, 34, 40))
            samples.append((font_name, line, style, vertical, size, font_path))
    if args.limit:
        rng.shuffle(samples)
        samples = samples[: args.limit]

    totals = defaultdict(lambda: [0, 0, 0, 0])  # chars, base errors, new errors, samples
    kanji = [0, 0, 0]
    base_time = new_time = 0.0
    rescued = broke = changed = 0
    examples = []
    save_dir = Path(args.save_dir) if args.save_dir else None
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    for number, (font_name, line, style, vertical, size, font_path) in enumerate(samples):
        image = compose(render(line, font_path, size, vertical), style, rng).convert("RGB")
        if save_dir and number < 60:
            image.save(save_dir / f"{number:03d}_{style}_{'v' if vertical else 'h'}.png")
        start = time.perf_counter()
        base = read_scored(ocr, image).text
        base_time += time.perf_counter() - start
        start = time.perf_counter()
        new = best_reading(ocr, image).text
        new_time += time.perf_counter() - start

        truth = normalise(line)
        base_errors = edit_distance(normalise(base), truth)
        new_errors = edit_distance(normalise(new), truth)
        for key in ("ALL", f"font:{font_name}", f"style:{style}", f"dir:{'vertical' if vertical else 'horizontal'}"):
            totals[key][0] += len(truth)
            totals[key][1] += base_errors
            totals[key][2] += new_errors
            totals[key][3] += 1
        kanji_truth = [c for c in truth if is_kanji(c)]
        kanji[0] += len(kanji_truth)
        kanji[1] += sum(1 for c in kanji_truth if c not in normalise(base))
        kanji[2] += sum(1 for c in kanji_truth if c not in normalise(new))
        if new != base:
            changed += 1
            rescued += new_errors < base_errors
            broke += new_errors > base_errors
            if len(examples) < 40:
                examples.append(f"  [{font_name}/{style}] {line}\n      before: {base}\n      after:  {new}")

    print(f"\nsamples: {len(samples)}   changed by enhancement: {changed}   better: {rescued}   worse: {broke}")
    print(f"time per sample: baseline {base_time / len(samples):.2f}s, enhanced {new_time / len(samples):.2f}s\n")
    print(f"{'group':<32}{'chars':>7}{'CER before':>12}{'CER after':>12}")
    for key in sorted(totals, key=lambda k: (k != "ALL", k)):
        chars, base_errors, new_errors, _ = totals[key]
        print(f"{key:<32}{chars:>7}{base_errors / chars:>11.1%}{new_errors / chars:>12.1%}")
    if kanji[0]:
        print(f"{'kanji missed':<32}{kanji[0]:>7}{kanji[1] / kanji[0]:>11.1%}{kanji[2] / kanji[0]:>12.1%}")
    print("\nchanged readings:")
    print("\n".join(examples))


if __name__ == "__main__":
    main()
