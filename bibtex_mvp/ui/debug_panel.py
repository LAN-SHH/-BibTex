from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QLineEdit, QWidget

from bibtex_mvp.application.orchestrator import ResolverConfig


def _build_editable_spinbox(min_value: float, max_value: float, default_value: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(min_value, max_value)
    spin.setDecimals(2)
    spin.setSingleStep(0.01)
    spin.setValue(default_value)
    spin.setLocale(QLocale.c())
    spin.setKeyboardTracking(False)
    spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    spin.setAlignment(Qt.AlignmentFlag.AlignRight)
    spin.setToolTip("可直接键盘输入，比如 0.85")
    line_edit: QLineEdit | None = spin.lineEdit()
    if line_edit is not None:
        line_edit.setReadOnly(False)
        line_edit.setPlaceholderText("范围 0.00 到 1.00")
    return spin


class DebugPanel(QGroupBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("开发调试面板", parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout()
        self.setLayout(layout)

        self.auto_accept_spin = _build_editable_spinbox(0.50, 1.00, 0.92)
        layout.addRow("自动通过阈值", self.auto_accept_spin)

        self.candidate_floor_spin = _build_editable_spinbox(0.30, 1.00, 0.80)
        layout.addRow("候选展示阈值", self.candidate_floor_spin)

    def to_config(self) -> ResolverConfig:
        return ResolverConfig(
            auto_accept_threshold=float(self.auto_accept_spin.value()),
            candidate_floor_threshold=float(self.candidate_floor_spin.value()),
            max_rows=20,
        )
