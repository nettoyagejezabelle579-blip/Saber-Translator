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


# 模型偶爾把「あ」「う…」「はぁはぁ」「びゅ～っ♡」原樣抄回來。
# 只由語氣詞／常見擬音組成的假名片段一定是聲音，直接換成中文寫法；
# 含其他假名的片段（人名、普通詞）不動。
_INTERJECTION_KANA = {
    "あ": "啊", "い": "咿", "う": "嗚", "え": "欸", "お": "喔", "ん": "嗯",
    "は": "哈", "ひ": "咿", "ふ": "呼", "へ": "嘿", "ほ": "齁",
    "ぁ": "啊", "ぃ": "咿", "ぅ": "嗚", "ぇ": "欸", "ぉ": "喔",
    "っ": "", "ー": "～",
}
# 常見擬音（漢化常用寫法），比對時取最長
_SFX_KANA = {
    "どぴゅ": "噗咻", "ぶぴゅ": "噗咻", "びゅる": "咻嚕", "びゅ": "咻", "ぴゅ": "咻",
    "ぐちゅ": "咕啾", "くちゅ": "咕啾", "ぬちゅ": "滋啾", "ずちゅ": "滋啾",
    "ちゅぱ": "啾啪", "ちゅ": "啾", "じゅぷ": "啾噗", "じゅぽ": "啾啵", "じゅる": "啾嚕",
    "ずぷ": "噗滋", "ずぶ": "噗滋", "ぬぷ": "噗", "ぐぽ": "咕啵", "ぱちゅ": "啪啾",
    "ぱん": "啪", "ごくん": "咕嘟", "ごく": "咕嘟", "どくん": "噗通", "どき": "撲通",
    "びくん": "抽搐", "びく": "抖", "ぶるん": "晃", "ぞく": "酥", "ぺろ": "舔",
    "れろ": "舔", "ぎゅ": "緊", "ぷしゃ": "噗咻", "ぶしゃ": "噴", "る": "嚕",
}
_SFX_MAX = max(len(unit) for unit in _SFX_KANA)
_SMALL_VOWELS = set("ぁぃぅぇぉ")
_GIGGLE_RE = re.compile(r"^(う?)(ふ{2,})$")
_KANA_RUN_RE = re.compile(r"[ぁ-ゖァ-ヺー]+")


def _to_hiragana(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def _convert_kana_run(run: str) -> str | None:
    core = run.replace("っ", "").replace("ー", "")
    giggle = _GIGGLE_RE.match(core)
    if giggle:  # ふふっ、うふふ → 呵呵
        return "呵" * len(giggle.group(2))
    out: list[str] = []
    after_sfx = False
    index = 0
    while index < len(run):
        for size in range(min(_SFX_MAX, len(run) - index), 0, -1):
            unit = run[index:index + size]
            if unit in _SFX_KANA and not (size == 1 and unit == "る" and not after_sfx):
                out.append(_SFX_KANA[unit])
                after_sfx = True
                index += size
                break
        else:
            char = run[index]
            if char not in _INTERJECTION_KANA:
                return None
            if char in _SMALL_VOWELS and after_sfx:
                out.append("～")  # びゅぅ → 咻～
            else:
                out.append(_INTERJECTION_KANA[char])
                if char not in "っー":
                    after_sfx = False
            index += 1
    return "".join(out)


def convert_leftover_interjections(text: str) -> str:
    """把譯文中殘留的日文語氣詞／擬音（あ、うっ、はぁ、びゅ～っ、ふふ…）轉成中文。"""

    def replace(match: re.Match) -> str:
        converted = _convert_kana_run(_to_hiragana(match.group()))
        return match.group() if converted is None else converted

    result = _KANA_RUN_RE.sub(replace, text)
    return re.sub(r"[～~]{2,}", "～", result)


def postprocess_translation(text: str, environ=os.environ) -> str:
    """譯文寫入氣泡前的統一後處理。"""
    if not isinstance(text, str) or not text.strip():
        return text
    region = configured_region(environ)
    if not region:
        return text
    text = convert_leftover_interjections(text)
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
    return to_traditional(convert_leftover_interjections(text), region)
