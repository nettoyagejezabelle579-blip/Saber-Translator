"""Interface language for the desktop control centre (Traditional Chinese by default).

The interface is written in Simplified Chinese. With ``zh-TW`` (the default)
every text shown by Qt is converted with OpenCC ``s2tw``: only the characters
change (设置 -> 設置, 视频 -> 視頻); the words stay the same, no regional
vocabulary is swapped in. ``zh-CN`` shows the original text.

The choice lives in ``data-v2/ui-language.txt`` so the strict desktop settings
file is untouched; the web interface gets the same choice through ``?lang=``
when the control centre opens it.
"""

from __future__ import annotations

from functools import lru_cache
import logging
from pathlib import Path
import re

LOGGER = logging.getLogger("saber.desktop.language")

TRADITIONAL = "zh-TW"
SIMPLIFIED = "zh-CN"
LANGUAGES = (TRADITIONAL, SIMPLIFIED)
LANGUAGE_LABELS = {TRADITIONAL: "繁體中文", SIMPLIFIED: "简体中文"}
LANGUAGE_FILE = "ui-language.txt"
_HAN = re.compile(r"[㐀-鿿]")

_active = TRADITIONAL


def read_language(data_root: Path) -> str:
    try:
        value = (Path(data_root) / LANGUAGE_FILE).read_text(encoding="utf-8-sig").strip()
    except OSError:
        return TRADITIONAL
    return value if value in LANGUAGES else TRADITIONAL


def write_language(data_root: Path, language: str) -> None:
    if language not in LANGUAGES:
        raise ValueError(f"unsupported interface language: {language!r}")
    path = Path(data_root) / LANGUAGE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(language + "\n", encoding="utf-8")


def active_language() -> str:
    return _active


def _converter():
    # 與譯文簡轉繁共用同一個 OpenCC（沒裝套件時用內附副本）；載入失敗就照常顯示原文。
    # s2tw：只換字（為、裡等常用繁體字形），不換成地區用語
    from src.shared.zh_hant import _converter as shared_converter

    return shared_converter("s2tw")


@lru_cache(maxsize=8192)
def _convert_cached(text: str) -> str:
    converter = _converter()
    if converter is None:
        return text
    return converter.convert(text)


def ui_text(text):
    """Text as it should be shown in the active interface language."""
    if _active != TRADITIONAL or not isinstance(text, str) or not _HAN.search(text):
        return text
    return _convert_cached(text)


# ---- Qt ------------------------------------------------------------------

def _wrap_first_text(cls, name: str, index: int = 0) -> None:
    original = getattr(cls, name, None)
    if original is None or getattr(original, "_saber_converted", False):
        return

    def wrapper(self, *args, **kwargs):
        if len(args) > index and isinstance(args[index], str):
            args = (*args[:index], ui_text(args[index]), *args[index + 1:])
        return original(self, *args, **kwargs)

    wrapper._saber_converted = True  # type: ignore[attr-defined]
    setattr(cls, name, wrapper)


def _wrap_static_texts(cls, name: str) -> None:
    original = getattr(cls, name, None)
    if original is None or getattr(original, "_saber_converted", False):
        return

    def wrapper(*args, **kwargs):
        args = tuple(ui_text(value) if isinstance(value, str) else value for value in args)
        return original(*args, **kwargs)

    wrapper._saber_converted = True  # type: ignore[attr-defined]
    setattr(cls, name, staticmethod(wrapper))


def convert_widget_texts(widget) -> None:
    """Convert the texts a widget already holds (set in its constructor)."""
    from PySide6.QtWidgets import (
        QAbstractButton,
        QComboBox,
        QGroupBox,
        QLabel,
        QLineEdit,
        QMenu,
        QMessageBox,
        QTabWidget,
        QTableWidget,
        QTreeWidget,
    )

    def fix(getter, setter):
        try:
            value = getter()
        except RuntimeError:
            return
        converted = ui_text(value)
        if converted != value:
            setter(converted)

    fix(widget.toolTip, widget.setToolTip)
    fix(widget.windowTitle, widget.setWindowTitle)
    fix(widget.accessibleName, widget.setAccessibleName)
    if isinstance(widget, (QLabel, QAbstractButton)):
        fix(widget.text, widget.setText)
    if isinstance(widget, QLineEdit):
        fix(widget.placeholderText, widget.setPlaceholderText)
    if isinstance(widget, QGroupBox):
        fix(widget.title, widget.setTitle)
    if isinstance(widget, QMessageBox):
        fix(widget.text, widget.setText)
        fix(widget.informativeText, widget.setInformativeText)
    if isinstance(widget, QComboBox):
        for row in range(widget.count()):
            fix(lambda row=row: widget.itemText(row), lambda value, row=row: widget.setItemText(row, value))
    if isinstance(widget, QTabWidget):
        for tab in range(widget.count()):
            fix(lambda tab=tab: widget.tabText(tab), lambda value, tab=tab: widget.setTabText(tab, value))
    if isinstance(widget, QMenu):
        fix(widget.title, widget.setTitle)
        for action in widget.actions():
            fix(action.text, action.setText)
            fix(action.toolTip, action.setToolTip)
    if isinstance(widget, QTableWidget):
        for column in range(widget.columnCount()):
            item = widget.horizontalHeaderItem(column)
            if item is not None:
                fix(item.text, item.setText)
    if isinstance(widget, QTreeWidget):
        header = widget.headerItem()
        if header is not None:
            for column in range(header.columnCount()):
                fix(lambda column=column: header.text(column), lambda value, column=column: header.setText(column, value))


def install_qt_conversion(app, language: str) -> None:
    """Convert every Qt text to the chosen language (call once, after QApplication)."""
    global _active
    _active = language if language in LANGUAGES else TRADITIONAL
    if _active != TRADITIONAL:
        return
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (
        QAbstractButton,
        QComboBox,
        QGroupBox,
        QLabel,
        QLineEdit,
        QMenu,
        QMessageBox,
        QSystemTrayIcon,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QWidget,
    )

    # 之後才設定的文字（狀態、通知、切換頁籤……）
    for cls, name, index in (
        (QLabel, "setText", 0),
        (QAbstractButton, "setText", 0),
        (QAction, "setText", 0),
        (QAction, "setToolTip", 0),
        (QWidget, "setToolTip", 0),
        (QWidget, "setWindowTitle", 0),
        (QWidget, "setAccessibleName", 0),
        (QLineEdit, "setPlaceholderText", 0),
        (QGroupBox, "setTitle", 0),
        (QMenu, "setTitle", 0),
        (QMenu, "addAction", 0),
        (QMenu, "addMenu", 0),
        (QMenu, "addSection", 0),
        (QComboBox, "addItem", 0),
        (QComboBox, "setItemText", 1),
        (QComboBox, "insertItem", 1),
        (QTabWidget, "addTab", 1),
        (QTabWidget, "setTabText", 1),
        (QTabWidget, "setTabToolTip", 1),
        (QMessageBox, "setText", 0),
        (QMessageBox, "setInformativeText", 0),
        (QSystemTrayIcon, "setToolTip", 0),
        (QSystemTrayIcon, "showMessage", 0),
        (QTableWidgetItem, "setText", 0),
    ):
        _wrap_first_text(cls, name, index)
    # showMessage(title, message, ...)：第二個也要轉
    _wrap_first_text(QSystemTrayIcon, "showMessage", 1)
    original_add_items = QComboBox.addItems

    def add_items(self, texts, *args, **kwargs):
        return original_add_items(self, [ui_text(text) for text in texts], *args, **kwargs)

    QComboBox.addItems = add_items
    original_headers = QTableWidget.setHorizontalHeaderLabels

    def set_headers(self, labels, *args, **kwargs):
        return original_headers(self, [ui_text(label) for label in labels], *args, **kwargs)

    QTableWidget.setHorizontalHeaderLabels = set_headers
    for name in ("question", "information", "warning", "critical", "about"):
        _wrap_static_texts(QMessageBox, name)

    # 建構時就帶入的文字：每個元件第一次顯示前（Polish）轉換一次
    class _PolishConverter(QObject):
        def eventFilter(self, watched, event):  # noqa: N802 (Qt API)
            if event.type() == QEvent.Type.Polish and isinstance(watched, QWidget):
                try:
                    convert_widget_texts(watched)
                except Exception:  # 轉換失敗不能影響介面
                    LOGGER.debug("轉換介面文字失敗", exc_info=True)
            return False

    app._saber_language_filter = _PolishConverter(app)
    app.installEventFilter(app._saber_language_filter)
