"""
繁體中文譯文後處理（台灣 / 香港）

大模型即使被要求輸出繁體，也常常混入簡體字或大陸用語、半形標點、“”引號等。
這裡在譯文寫入氣泡之前統一做一次規範化：

1. 簡轉繁（OpenCC）：台灣用 s2twp（含詞彙，如 软件→軟體），香港用 s2hk。
   已經是繁體的文字基本不會被改動。
2. 標點：“”→「」、‘’→『』、成對的 "" → 「」、半形 !?,;: → 全形、
   ... / ・・・ / 單個 … → ……、~ → ～。
   直排時「」『』會被渲染器轉成直排引號，比“”自然得多。

環境變數 SABER_ZH_HANT_REGION 可選 tw（預設）、hk、off（關閉全部後處理）。
優先使用已安裝的 opencc 套件；未安裝時改用 src/third_party/opencc 內附的副本，
保證簡轉繁一定會執行。
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache

logger = logging.getLogger("ZhHant")

REGION_ENV = "SABER_ZH_HANT_REGION"
_OPENCC_CONFIGS = {"tw": "s2twp", "hk": "s2hk"}

_CJK = r"぀-ヿ㐀-䶿一-鿿豈-﫿＀-￯　-〿"
_CJK_RE = re.compile(f"[{_CJK}]")
_HALF_TO_FULL = {"!": "！", "?": "？", ",": "，", ";": "；", ":": "："}
_HALF_PUNCT_RE = re.compile(r"[!?,;:]")
_ASCII_WORD = re.compile(r"[A-Za-z0-9]")


def configured_region(environ=os.environ) -> str | None:
    region = str(environ.get(REGION_ENV, "tw")).strip().lower()
    if region in ("", "off", "0", "none", "false"):
        return None
    if region not in _OPENCC_CONFIGS:
        logger.warning("%s=%r 無效，改用 tw", REGION_ENV, region)
        return "tw"
    return region


def _opencc_class():
    try:
        from opencc import OpenCC
        return OpenCC
    except ImportError:
        pass
    try:
        from src.third_party.opencc import OpenCC
        return OpenCC
    except ImportError:
        logger.error("找不到 OpenCC（內附副本也遺失），譯文無法簡轉繁")
        return None


@lru_cache(maxsize=4)
def _converter(config: str):
    opencc_class = _opencc_class()
    if opencc_class is None:
        return None
    for name in (config, f"{config}.json"):
        try:
            return opencc_class(name)
        except Exception:
            continue
    logger.warning("OpenCC 無法載入配置 %s", config)
    return None


def _convert_half_width(text: str) -> str:
    chars = list(text)
    for match in _HALF_PUNCT_RE.finditer(text):
        i = match.start()
        prev_c = text[i - 1] if i > 0 else ""
        next_c = text[i + 1] if i + 1 < len(text) else ""
        # 1,000 / 12:30 / abc!def 這類純 ASCII 上下文保持不變
        if _ASCII_WORD.match(prev_c or " ") and _ASCII_WORD.match(next_c or " "):
            continue
        chars[i] = _HALF_TO_FULL[match.group()]
    return "".join(chars)


def normalize_punctuation(text: str) -> str:
    if not _CJK_RE.search(text):
        return text
    text = text.replace("“", "「").replace("”", "」")
    text = text.replace("‘", "『").replace("’", "』")
    text = re.sub(r'"([^"\n]*)"', r"「\1」", text)
    text = re.sub(r"(?:\.{3,}|・{2,}|。{3,}|…+)", "……", text)
    text = text.replace("~", "～").replace("〜", "～")
    return _convert_half_width(text)


def to_traditional(text: str, region: str | None = None) -> str:
    region = configured_region() if region is None else region
    if not region:
        return text
    converter = _converter(_OPENCC_CONFIGS[region])
    if converter is None:
        return text
    return converter.convert(text)


def postprocess_translation(text: str, environ=os.environ) -> str:
    """譯文寫入氣泡前的統一後處理。"""
    if not isinstance(text, str) or not text.strip():
        return text
    region = configured_region(environ)
    if not region:
        return text
    return normalize_punctuation(to_traditional(text, region))


def ensure_traditional_for_render(text: str, environ=os.environ) -> str:
    """渲染前最後一道保險：只做簡轉繁，不改標點。

    覆蓋使用者手動輸入、舊專案、外部匯入等沒有經過翻譯後處理的文字。
    已經是繁體的文字不會被改動。
    """
    if not isinstance(text, str) or not _CJK_RE.search(text):
        return text
    region = configured_region(environ)
    if not region:
        return text
    return to_traditional(text, region)
