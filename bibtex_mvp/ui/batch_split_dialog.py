from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

_DIALOG_STYLE = """
QDialog {
    background: #f3f7fb;
    border: 1px solid #dbe4f3;
    border-radius: 10px;
}
QLabel {
    color: #1a2436;
}
QLabel#DialogTitle {
    color: #13233c;
    font-size: 18px;
    font-weight: 700;
}
QLabel#DialogHint {
    color: #526480;
    font-size: 12px;
}
QPlainTextEdit {
    background: #ffffff;
    color: #111827;
    border: 1px solid #c7d3e8;
    border-radius: 8px;
    padding: 6px;
}
QScrollArea {
    background: #ffffff;
    border: 1px solid #c7d3e8;
    border-radius: 8px;
}
QPushButton {
    background: #ecf3ff;
    color: #142847;
    border: 1px solid #cfddf4;
    border-radius: 8px;
    padding: 7px 12px;
    min-width: 92px;
    min-height: 32px;
}
QPushButton:hover {
    background: #deebff;
    border: 1px solid #b8cdef;
}
QPushButton:pressed {
    background: #ccdfff;
    border: 1px solid #9ab7e4;
}
"""


def _normalize_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


@dataclass(slots=True)
class AmbiguousItemEditor:
    index: int
    editor: QPlainTextEdit


class AmbiguousSplitDialog(QDialog):
    def __init__(self, items: list[str], ambiguous_indexes: list[int], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("分条确认")
        self.resize(920, 620)
        self.setMinimumSize(760, 500)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(_DIALOG_STYLE)
        self._all_items = items
        self._ambiguous_indexes = ambiguous_indexes
        self._editors: list[AmbiguousItemEditor] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("请确认分条结果")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        hint = QLabel(
            "以下条目可能包含多条参考文献。\n"
            "1. 每行保留一条文献\n"
            "2. 可以直接修改或拆分内容\n"
            "3. DOI 建议保留在对应条目中\n"
            "4. 留空会导致该条无法继续处理"
        )
        hint.setObjectName("DialogHint")
        root.addWidget(hint)

        container = QWidget()
        form = QFormLayout(container)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        for index in self._ambiguous_indexes:
            editor = QPlainTextEdit()
            editor.setPlainText(self._all_items[index - 1])
            editor.setMinimumHeight(96)
            form.addRow(QLabel(f"条目 {index}"), editor)
            self._editors.append(AmbiguousItemEditor(index=index, editor=editor))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def accept(self) -> None:
        for item in self._editors:
            if not _normalize_lines(item.editor.toPlainText()):
                QMessageBox.warning(self, "内容为空", f"条目 {item.index} 不能为空，请至少保留一行。")
                return
        super().accept()

    def merged_items(self) -> list[str]:
        replacements: dict[int, list[str]] = {}
        for item in self._editors:
            replacements[item.index] = _normalize_lines(item.editor.toPlainText())

        merged: list[str] = []
        for index, original in enumerate(self._all_items, start=1):
            if index in replacements:
                merged.extend(replacements[index])
            else:
                merged.append(original)
        return [line for line in merged if line.strip()]


class ManualSplitDialog(QDialog):
    def __init__(self, raw_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("手动分条")
        self.resize(860, 500)
        self.setMinimumSize(720, 420)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(_DIALOG_STYLE)
        self._editor = QPlainTextEdit()
        self._editor.setPlainText(raw_text)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("手动编辑分条")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        hint = QLabel("请按一行一条参考文献的格式整理内容。")
        hint.setObjectName("DialogHint")
        root.addWidget(hint)

        root.addWidget(self._editor, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def accept(self) -> None:
        if not self.lines():
            QMessageBox.warning(self, "内容为空", "请至少保留一条参考文献。")
            return
        super().accept()

    def lines(self) -> list[str]:
        return _normalize_lines(self._editor.toPlainText())
