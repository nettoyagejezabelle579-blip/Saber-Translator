"""
單獨語氣詞／呻吟氣泡的判斷

整個氣泡只有「あ」「うん」「はぁはぁ」「んっ…♡」這類語氣詞或呻吟時，
保留原圖的日文：不翻譯、不去字、不嵌字。和其他對白寫在同一個氣泡裡的語氣詞照常翻譯。

判斷規則（全部滿足才跳過）：
1. 去掉標點與符號（ー～…！？♡ 等）後，片假名先轉成平假名；
2. 只剩母音（あいうえお 及小寫）、ん、っ，以及は行（はひふへほ，用於喘息）；
3. 長度不超過 MAX_KANA，且至少一半是母音／ん／っ（排除「ふふ」「へへ」等笑聲以外的詞）；
4. 不是「はい」「いい」「いいえ」「おい」「ううん」等有實際意思的詞。
只剩標點（例如「……」「！？」）的氣泡也會跳過。

環境變數 SABER_KEEP_STANDALONE_SFX=0 可關閉此功能。
"""

from __future__ import annotations

import os
import re

ENV_SWITCH = "SABER_KEEP_STANDALONE_SFX"
MAX_KANA = 6

_STRIP_RE = re.compile(
    r"[\s　ー〜～~・･…‥。、，,．.！？!?♡♥❤❣☆★♪・「」『』（）()【】\-—―゛゜\"'“”‘’]+"
)
_VOWELS = set("あいうえおぁぃぅぇぉんっ")
_BREATH = set("はひふへほ")
_MEANINGFUL = {
    "はい", "いい", "いいえ", "いえ", "おい", "ううん", "へい", "あい", "うい",
    "ほい",
}


def _to_hiragana(text: str) -> str:
    return "".join(
        chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text
    )


def is_enabled(environ=os.environ) -> bool:
    return str(environ.get(ENV_SWITCH, "1")).strip().lower() not in {
        "0", "off", "false", "no",
    }


def is_standalone_sfx(text: object, environ=os.environ) -> bool:
    """整個氣泡只有語氣詞／呻吟（或只有標點）時回傳 True。"""
    if not isinstance(text, str) or not text.strip() or not is_enabled(environ):
        return False
    core = _to_hiragana(_STRIP_RE.sub("", text))
    if not core:
        return True
    if len(core) > MAX_KANA or core in _MEANINGFUL:
        return False
    if any(c not in _VOWELS and c not in _BREATH for c in core):
        return False
    vowel_count = sum(1 for c in core if c in _VOWELS)
    return vowel_count * 2 >= len(core)
