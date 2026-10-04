"""OCR 準確度：低信心時重讀、挑最有把握的結果；翻譯提示詞附上錯字還原規則。"""

from __future__ import annotations

import numpy as np
from PIL import Image

from src.interfaces import manga_ocr_enhance as enhance
from src.interfaces.manga_ocr_enhance import Reading


def _fake_reader(scores_by_view, beam_score=None):
    calls = []

    def read(ocr, image, *, view="orig", num_beams=1):
        calls.append((view, num_beams))
        if num_beams > 1:
            return Reading(f"{view}-beam", beam_score, view, num_beams)
        return Reading(view, scores_by_view.get(view, -5.0), view, 1)

    return read, calls


def _crop(width=60, height=200, background=255, ink=0):
    array = np.full((height, width), background, dtype=np.uint8)
    array[20:180, 25:35] = ink
    return Image.fromarray(array).convert("RGB")


def test_confident_first_reading_is_kept(monkeypatch):
    read, calls = _fake_reader({"orig": -0.01})
    monkeypatch.setattr(enhance, "read_scored", read)
    assert enhance.best_reading(object(), _crop()).text == "orig"
    assert calls == [("orig", 1)]


def test_low_confidence_reads_other_views_and_keeps_best(monkeypatch):
    read, calls = _fake_reader({"orig": -0.9, "pad": -0.5, "contrast": -0.05, "binary": -0.3})
    monkeypatch.setattr(enhance, "read_scored", read)
    best = enhance.best_reading(object(), _crop())
    assert best.text == "contrast"
    # 一旦有足夠把握就停止，不再多讀
    assert ("binary", 1) not in calls


def test_beam_search_is_last_resort(monkeypatch):
    read, calls = _fake_reader({"orig": -0.9, "pad": -0.8, "contrast": -0.7, "binary": -0.6}, beam_score=-0.2)
    monkeypatch.setattr(enhance, "read_scored", read)
    best = enhance.best_reading(object(), _crop())
    assert best.text == "binary-beam"
    assert calls[-1] == ("binary", 4)


def test_worse_beam_result_is_ignored(monkeypatch):
    read, _ = _fake_reader({"orig": -0.4, "pad": -0.8, "contrast": -0.7, "binary": -0.6}, beam_score=-0.9)
    monkeypatch.setattr(enhance, "read_scored", read)
    assert enhance.best_reading(object(), _crop()).text == "orig"


def test_white_text_on_dark_background_is_inverted():
    views = dict(enhance.candidate_views(_crop(background=20, ink=240)))
    pad = np.asarray(views["pad"])
    assert pad[0, 0] > 200  # 背景變白
    assert pad[pad.shape[0] // 2, pad.shape[1] // 2] < 60  # 字變黑


def test_binarised_view_removes_screentone():
    array = np.full((200, 60), 255, dtype=np.uint8)
    array[::4, ::4] = 150  # 網點
    array[20:180, 25:35] = 0
    binary = np.asarray(dict(enhance.candidate_views(Image.fromarray(array)))["binary"])
    assert set(np.unique(binary)) <= {0, 255}
    assert (binary == 0).sum() < 2500  # 只剩文字，網點不會變成黑點


def test_small_crops_get_an_upscaled_view():
    assert "upscale" in dict(enhance.candidate_views(_crop(width=30, height=40)))
    assert "upscale" not in dict(enhance.candidate_views(_crop()))


def test_translation_prompt_gets_ocr_guidance(monkeypatch):
    from src.core import translation
    from src.shared import constants

    guided = translation.with_ocr_guidance("你是翻譯。")
    assert guided.startswith("你是翻譯。") and "OCR 錯字還原" in guided and "未/末" in guided
    assert translation.with_ocr_guidance(guided) == guided  # 不重複附加
    assert translation.with_ocr_guidance("") == ""
    monkeypatch.setattr(constants, "OCR_CORRECTION_IN_PROMPT", False)
    assert translation.with_ocr_guidance("你是翻譯。") == "你是翻譯。"


def test_batch_messages_include_ocr_guidance_for_saved_prompts():
    from src.core import translation

    for json_mode in (False, True):
        messages, _ = translation._assemble_batch_prompt(["テスト"], "舊版自訂提示詞", json_mode)
        assert messages[0]["role"] == "system"
        assert messages[0]["content"].startswith("舊版自訂提示詞")
        assert "OCR 錯字還原" in messages[0]["content"]
