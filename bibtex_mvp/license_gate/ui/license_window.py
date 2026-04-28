from __future__ import annotations

from PySide6.QtCore import Signal
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


class LicenseWindow(QMainWindow):
    activated = Signal()

    def __init__(self, manager: LicenseManager, initial_result: LicenseCheckResult) -> None:
        super().__init__()
        self.manager = manager
        self.setWindowTitle("许可证验证")
        self.resize(760, 520)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        self.tip_label = QLabel("请输入许可证字符串，或导入许可证文件。")
        layout.addWidget(self.tip_label)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("粘贴许可证 JSON 内容")
        layout.addWidget(self.input_edit)

        btn_row = QHBoxLayout()
        layout.addLayout(btn_row)

        import_btn = QPushButton("导入许可证文件")
        import_btn.clicked.connect(self._on_import_clicked)
        btn_row.addWidget(import_btn)

        verify_btn = QPushButton("验证并进入主程序")
        verify_btn.clicked.connect(self._on_verify_clicked)
        btn_row.addWidget(verify_btn)

        quit_btn = QPushButton("退出")
        quit_btn.clicked.connect(self.close)
        btn_row.addWidget(quit_btn)

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
            QMessageBox.warning(self, "读取失败", f"无法读取文件\n{exc}")
            return
        self.input_edit.setPlainText(text)

    def _on_verify_clicked(self) -> None:
        license_text = self.input_edit.toPlainText().strip()
        if not license_text:
            QMessageBox.warning(self, "输入为空", "请先粘贴或导入许可证。")
            return
        result = self.manager.validate_and_store(license_text)
        self._show_result(result)
        if result.ok:
            QMessageBox.information(self, "验证成功", "许可证已保存，将进入主程序。")
            self.activated.emit()
            self.close()

    def _show_result(self, result: LicenseCheckResult) -> None:
        if result.ok:
            self.status_label.setText("状态: 本地许可证有效")
            self.status_label.setStyleSheet("color: #0f8f2f;")
            return
        code = result.error_code or "UNKNOWN"
        self.status_label.setText(f"状态: {code}  {result.message}")
        self.status_label.setStyleSheet("color: #c62828;")
