from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..manager import LicenseManager
from ..models import LicenseCheckResult

_LICENSE_WINDOW_STYLE = """
QWidget {
    background: #edf2f7;
    color: #18263d;
}
QWidget#LicenseRoot {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eef3f8, stop:1 #e8eef6);
}
QWidget#HeaderCard,
QWidget#BodyCard,
QWidget#ActionCard {
    background: rgba(255, 255, 255, 0.96);
    border: 1px solid #d6deea;
    border-radius: 16px;
}
QLabel#Eyebrow {
    color: #607089;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
QLabel#Title {
    color: #12253f;
    font-size: 28px;
    font-weight: 700;
}
QLabel#Subtitle {
    color: #53657f;
    font-size: 13px;
    line-height: 1.5;
}
QLabel#StatusOK {
    background: #e8f6ec;
    color: #186536;
    border: 1px solid #bee2c8;
    border-radius: 10px;
    padding: 8px 10px;
    font-weight: 600;
}
QLabel#StatusERR {
    background: #fff0f0;
    color: #a23434;
    border: 1px solid #f0c6c6;
    border-radius: 10px;
    padding: 8px 10px;
    font-weight: 600;
}
QPlainTextEdit {
    background: #fbfcfe;
    color: #0f1f34;
    border: 1px solid #cad6e5;
    border-radius: 12px;
    padding: 10px 12px;
    selection-background-color: #dbe8f7;
}
QPlainTextEdit:focus {
    border: 1px solid #8da8ca;
}
QPushButton {
    background: #eef4fb;
    color: #173252;
    border: 1px solid #c7d4e4;
    border-radius: 10px;
    padding: 8px 14px;
    min-width: 124px;
    min-height: 36px;
    font-weight: 600;
}
QPushButton:hover {
    background: #e2ecf8;
    border: 1px solid #afc3db;
}
QPushButton:pressed {
    background: #d5e4f5;
}
QPushButton#PrimaryButton {
    background: #173a67;
    color: #f8fbff;
    border: 1px solid #173a67;
}
QPushButton#PrimaryButton:hover {
    background: #224a7e;
    border: 1px solid #224a7e;
}
"""


class LicenseWindow(QMainWindow):
    activated = Signal()

    def __init__(self, manager: LicenseManager, initial_result: LicenseCheckResult) -> None:
        super().__init__()
        self.manager = manager
        self.setWindowTitle("许可证验证")
        self.resize(860, 620)
        self.setMinimumSize(760, 560)
        self.setStyleSheet(_LICENSE_WINDOW_STYLE)

        root = QWidget()
        root.setObjectName("LicenseRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header_card = QWidget()
        header_card.setObjectName("HeaderCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(6)

        eyebrow = QLabel("License Gate")
        eyebrow.setObjectName("Eyebrow")
        title = QLabel("导入许可证并进入工作台")
        title.setObjectName("Title")
        subtitle = QLabel(
            "当前版本使用本地许可证验证。导入或粘贴许可证 JSON 内容，验证通过后即可进入 BibTeX 整理主界面。"
        )
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)

        header_layout.addWidget(eyebrow)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header_card)

        body_card = QWidget()
        body_card.setObjectName("BodyCard")
        body_layout = QVBoxLayout(body_card)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(10)

        self.status_label = QLabel("")
        body_layout.addWidget(self.status_label)

        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("请粘贴许可证 JSON 内容")
        body_layout.addWidget(self.input_edit, 1)
        layout.addWidget(body_card, 1)

        action_card = QWidget()
        action_card.setObjectName("ActionCard")
        action_layout = QHBoxLayout(action_card)
        action_layout.setContentsMargins(14, 12, 14, 12)
        action_layout.setSpacing(10)

        import_btn = QPushButton("导入许可证文件")
        import_btn.clicked.connect(self._on_import_clicked)
        action_layout.addWidget(import_btn)

        verify_btn = QPushButton("验证并进入主程序")
        verify_btn.setObjectName("PrimaryButton")
        verify_btn.clicked.connect(self._on_verify_clicked)
        action_layout.addWidget(verify_btn)

        quit_btn = QPushButton("退出")
        quit_btn.clicked.connect(self.close)
        action_layout.addWidget(quit_btn)
        action_layout.addStretch(1)
        layout.addWidget(action_card)

        self._show_result(initial_result)

    def _on_import_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择许可证文件",
            "",
            "JSON 文件 (*.json);;文本文件 (*.txt);;所有文件 (*)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            QMessageBox.warning(self, "读取失败", f"无法读取许可证文件。\n{exc}")
            return
        self.input_edit.setPlainText(text)

    def _on_verify_clicked(self) -> None:
        license_text = self.input_edit.toPlainText().strip()
        if not license_text:
            QMessageBox.warning(self, "内容为空", "请先输入或导入许可证内容。")
            return
        result = self.manager.validate_and_store(license_text)
        self._show_result(result)
        if result.ok:
            QMessageBox.information(self, "验证成功", "许可证已保存，应用将进入主界面。")
            self.activated.emit()
            self.close()

    def _show_result(self, result: LicenseCheckResult) -> None:
        if result.ok:
            self.status_label.setObjectName("StatusOK")
            self.status_label.setText("验证通过，许可证可用。")
        else:
            code = result.error_code or "UNKNOWN"
            self.status_label.setObjectName("StatusERR")
            self.status_label.setText(f"验证失败，错误码 {code}。{result.message}")

        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
