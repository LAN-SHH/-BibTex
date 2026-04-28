from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from bibtex_mvp.ui.main_window import MainWindow

from .manager import LicenseManager
from .models import LicenseCheckResult
from .ui import LicenseWindow


class AppBootstrap:
    def __init__(self) -> None:
        self.app = QApplication(sys.argv)
        self.license_manager = LicenseManager()
        self.main_window: MainWindow | None = None
        self.license_window: LicenseWindow | None = None

    def run(self) -> int:
        local_result = self.license_manager.validate_local_license()
        if local_result.ok:
            self._show_main()
        else:
            self._show_license_window(local_result)
        return self.app.exec()

    def _show_main(self) -> None:
        self.main_window = MainWindow()
        self.main_window.show()

    def _show_license_window(self, initial_result: LicenseCheckResult) -> None:
        self.license_window = LicenseWindow(self.license_manager, initial_result)
        self.license_window.activated.connect(self._show_main)
        self.license_window.show()

