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
