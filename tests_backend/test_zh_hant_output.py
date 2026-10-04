from src.core.rendering import _kinsoku_split
from src.shared.zh_hant import normalize_punctuation, postprocess_translation


def test_simplified_leaks_are_converted_for_taiwan():
    assert postprocess_translation("这个软件里面", {}) == "這個軟體裡面"


def test_hong_kong_region():
    assert postprocess_translation("里面", {"SABER_ZH_HANT_REGION": "hk"}) == "裏面"


def test_disabled_region_leaves_text_untouched():
    assert postprocess_translation("里面...", {"SABER_ZH_HANT_REGION": "off"}) == "里面..."


def test_traditional_text_is_stable():
    text = "「我、我已經……不行了♡」"
    assert postprocess_translation(text, {}) == text


def test_punctuation_normalization():
    assert normalize_punctuation("“不要...”") == "「不要……」"
    assert normalize_punctuation("真的嗎?好~") == "真的嗎？好～"
    assert normalize_punctuation("1,000日圓") == "1,000日圓"
    assert normalize_punctuation("Hello, world!") == "Hello, world!"


def test_kinsoku_pushes_previous_char_with_closing_punctuation():
    assert _kinsoku_split("我不要", "。") == ("我不", "要")
    assert _kinsoku_split("好舒服", "」") == ("好舒", "服")


def test_kinsoku_moves_opening_bracket_to_next_line():
    assert _kinsoku_split("他說「", "不") == ("他說", "「")


def test_kinsoku_leaves_normal_breaks_alone():
    assert _kinsoku_split("我不要", "你") == ("我不要", "")
    assert _kinsoku_split("我", "。") == ("我", "")


def test_vendored_opencc_is_used_when_package_missing(monkeypatch):
    import builtins

    from src.shared import zh_hant

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "opencc" and level == 0:
            raise ImportError(name)
        return real_import(name, globals, locals, fromlist, level)

    zh_hant._converter.cache_clear()
    monkeypatch.setattr(builtins, "__import__", fake_import)
    try:
        assert zh_hant.postprocess_translation("这个软件", {}) == "這個軟體"
    finally:
        zh_hant._converter.cache_clear()


def test_render_safety_net_converts_manual_simplified_edits():
    from src.shared.zh_hant import ensure_traditional_for_render

    assert ensure_traditional_for_render("头发湿了", {}) == "頭髮溼了"
    assert ensure_traditional_for_render("「已經……」", {}) == "「已經……」"
    assert ensure_traditional_for_render("OK!", {}) == "OK!"
    assert ensure_traditional_for_render("头发", {"SABER_ZH_HANT_REGION": "off"}) == "头发"


def test_leftover_interjection_kana_becomes_chinese():
    assert postprocess_translation("う、あ。。。", {}) == "嗚、啊……"
    assert postprocess_translation("はぁはぁ", {}) == "哈啊哈啊"
    assert postprocess_translation("好舒服…あっ♡", {}) == "好舒服……啊♡"


def test_kana_words_that_are_not_interjections_are_left_alone():
    assert postprocess_translation("ユキ…", {}) == "ユキ……"
    # 譯文裡殘留的常見日文詞會換成中文
    assert postprocess_translation("ダメ", {}) == "不行"


def test_render_safety_net_also_fixes_old_translations():
    from src.shared.zh_hant import ensure_traditional_for_render

    assert ensure_traditional_for_render("あっ…", {}) == "啊…"


def test_user_reported_leftover_sound_words():
    # 實際翻譯後殘留在氣泡裡的日文（使用者回報）
    assert postprocess_translation("びゅー", {}) == "咻～"
    assert postprocess_translation("うっ……", {}) == "嗚……"
    assert postprocess_translation("んっ♡んん", {}) == "嗯♡嗯嗯"
    assert postprocess_translation("びゅぅ～っ♡", {}) == "咻～♡"
    assert postprocess_translation("ふふっ", {}) == "呵呵"


def test_common_onomatopoeia_left_in_translation():
    assert postprocess_translation("ドピュッ", {}) == "噗咻"
    assert postprocess_translation("ぐちゅぐちゅ", {}) == "咕啾咕啾"
    assert postprocess_translation("パンパンッ", {}) == "啪啪"


def test_more_user_reported_leftovers():
    cases = {
        "とぷとぷ……♡": "咕嘟咕嘟……♡",
        "あー・・・": "啊～……",
        "ぎゅーっ": "緊～",
        "びゅるるる♡": "咻嚕嚕嚕♡",
        "ぐっ……": "唔……",
        "ぱんぱん": "啪啪",
        "うぅ……っ": "嗚嗚……",
        "ん～～": "嗯～",
        "精子びゅー": "精子咻～",
        "びゅ～～っ♡": "咻～♡",
    }
    for source, expected in cases.items():
        assert postprocess_translation(source, {}) == expected, source


def test_untranslated_lines_get_common_words_and_trailing_sounds_fixed():
    assert postprocess_translation("中出しびゅーっ♡", {}) == "內射咻～♡"
    assert postprocess_translation("あっ…イク…うぅ～っ♡", {}) == "啊……去了……嗚嗚～♡"


def test_real_japanese_words_are_not_turned_into_sounds():
    for word in ("ずるい", "ありがとう", "かぶる", "ちょっと"):
        assert postprocess_translation(word, {}) == word


def test_refusal_is_reported_clearly():
    import pytest

    from src.core.translation import TranslationParseException, _parse_batch_response

    with pytest.raises(TranslationParseException, match="模型拒絕翻譯"):
        _parse_batch_response("你好，我无法给到相关内容。", 4)
    with pytest.raises(TranslationParseException, match="编号格式"):
        _parse_batch_response("隨便一段沒有編號的文字", 4)


def test_untranslated_sentences_are_left_whole_and_flagged_for_retry():
    from src.shared.zh_hant import has_untranslated_japanese

    for sentence in (
        "頬肉と舌がにゅるにゆる動くっ",
        "ちんちんのゾワゾワやばいこんなのすぐイっちゃう．．．ッ",
    ):
        # 不逐段亂轉（不會出現「動唔」「すぐ要去了」），而是整句交給重新翻譯
        assert postprocess_translation(sentence, {}).startswith(sentence[:4])
        assert has_untranslated_japanese(sentence)
    assert not has_untranslated_japanese("臉頰的肉和舌頭滑溜溜地蠕動著")
    assert not has_untranslated_japanese("ユキ…")
    assert not has_untranslated_japanese("內射咻～♡")


def test_pipeline_retranslates_bubbles_left_in_japanese():
    from types import SimpleNamespace

    from src.backend_v2.translation.pipeline import TranslationPipelineService

    calls = []

    def translate(texts, section, mode):
        calls.append(list(texts))
        if texts == ["拒絕"]:
            raise RuntimeError("模型拒絕翻譯這一頁")
        return {"translated": ["臉頰的肉和舌頭滑溜溜地蠕動著"], "textbox": []}

    service = SimpleNamespace(algorithms=SimpleNamespace(translate=translate))
    result = TranslationPipelineService._retranslate_leftover_japanese(
        service,
        ["好舒服", "頬肉と舌がにゅるにゆる動くっ", "まだ日本語のまま"],
        ["原文1", "原文2", "拒絕"],
        {},
        "batch",
    )
    assert result == ["好舒服", "臉頰的肉和舌頭滑溜溜地蠕動著", "まだ日本語のまま"]
    assert calls == [["原文2"], ["拒絕"]]
