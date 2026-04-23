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
        self.resize(860, 560)
        self._all_items = items
        self._ambiguous_indexes = ambiguous_indexes
        self._editors: list[AmbiguousItemEditor] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        self.setLayout(root)
        root.addWidget(
            QLabel(
                "请只修正有歧义的条目。标准\n"
                "1. 一行一条文献\n"
                "2. 尽量包含作者、年份、标题\n"
                "3. 可包含 DOI\n"
                "4. 同一条文献不要拆成两行"
            )
        )

        container = QWidget()
        form = QFormLayout()
        container.setLayout(form)
        for index in self._ambiguous_indexes:
            editor = QPlainTextEdit()
            editor.setPlainText(self._all_items[index - 1])
            editor.setMinimumHeight(90)
            form.addRow(QLabel(f"原始编号 {index}"), editor)
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
                QMessageBox.warning(self, "内容为空", f"原始编号 {item.index} 需要至少一条非空文献")
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
        self.setWindowTitle("手动分条编辑")
        self.resize(860, 460)
        self._editor = QPlainTextEdit()
        self._editor.setPlainText(raw_text)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        self.setLayout(root)
        root.addWidget(QLabel("请按一行一条文献编辑，程序将按行处理。"))
        root.addWidget(self._editor, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def accept(self) -> None:
        if not self.lines():
            QMessageBox.warning(self, "内容为空", "请至少保留一条文献")
            return
        super().accept()

    def lines(self) -> list[str]:
        return _normalize_lines(self._editor.toPlainText())

