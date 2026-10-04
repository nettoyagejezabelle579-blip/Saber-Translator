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


def test_low_confidence_reads_measured_views_and_keeps_best(monkeypatch):
    read, calls = _fake_reader({"orig": -0.9, "contrast": -0.5, "binary": -0.03, "square": -0.3})
    monkeypatch.setattr(enhance, "read_scored", read)
    best = enhance.best_reading(object(), _crop())
    assert best.text == "binary"
    # 只讀評測選出的三種圖，不讀加粗／留白
    assert [view for view, _ in calls] == ["orig", "contrast", "binary", "square"]


def test_beam_search_is_off_by_default(monkeypatch):
    read, calls = _fake_reader({"orig": -0.9, "contrast": -0.8, "binary": -0.7, "square": -0.6}, beam_score=-0.1)
    monkeypatch.setattr(enhance, "read_scored", read)
    assert enhance.best_reading(object(), _crop()).text == "square"
    assert all(beams == 1 for _, beams in calls)


def test_beam_search_can_be_enabled(monkeypatch):
    read, calls = _fake_reader({"orig": -0.9, "contrast": -0.8, "binary": -0.7, "square": -0.6}, beam_score=-0.2)
    monkeypatch.setattr(enhance, "read_scored", read)
    assert enhance.best_reading(object(), _crop(), beams=4).text == "square-beam"
    assert calls[-1] == ("square", 4)


def test_original_reading_kept_when_views_are_less_confident(monkeypatch):
    read, _ = _fake_reader({"orig": -0.4, "contrast": -0.8, "binary": -0.7, "square": -0.6})
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
