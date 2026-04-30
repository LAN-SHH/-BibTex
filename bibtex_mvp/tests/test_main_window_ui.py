import os

import pytest
from PySide6.QtWidgets import QApplication

from bibtex_mvp.domain.models import CandidateRecord
from bibtex_mvp.ui.main_window import MainWindow
from bibtex_mvp.ui.widgets import CandidateTable, ResultTable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_scholar_button_is_hidden_on_startup(qapp: QApplication) -> None:
    _ = qapp
    window = MainWindow()
    assert window.scholar_btn.isHidden()


def test_selected_entry_detail_widgets_are_removed(qapp: QApplication) -> None:
    _ = qapp
    window = MainWindow()
    assert not hasattr(window, "raw_input_line")
    assert not hasattr(window, "title_line")
    assert not hasattr(window, "authors_line")
    assert not hasattr(window, "year_line")
    assert not hasattr(window, "doi_line")
    assert not hasattr(window, "status_line")


def test_debug_panel_is_removed_and_thresholds_come_from_constructor(qapp: QApplication) -> None:
    _ = qapp
    window = MainWindow(auto_accept_threshold=0.88, candidate_floor_threshold=0.73)
    assert not hasattr(window, "debug_panel")
    assert window.auto_accept_threshold == pytest.approx(0.88)
    assert window.candidate_floor_threshold == pytest.approx(0.73)


def test_result_table_header_widths_stay_fixed_after_reload(qapp: QApplication) -> None:
    _ = qapp
    table = ResultTable()
    initial_widths = [table.columnWidth(i) for i in range(table.columnCount())]
    table.load_rows(
        [
            {"index": 1, "title": "Short", "authors": "A", "year": "2024", "doi": "10.1/a", "message": "ok"},
            {
                "index": 2,
                "title": "A very long title that would previously force the header to shift when columns resized",
                "authors": "Author One, Author Two",
                "year": "2025",
                "doi": "10.1/very-long-doi-value",
                "message": "needs manual check",
            },
        ]
    )
    reloaded_widths = [table.columnWidth(i) for i in range(table.columnCount())]
    assert reloaded_widths == initial_widths


def test_candidate_table_header_widths_stay_fixed_after_reload(qapp: QApplication) -> None:
    _ = qapp
    table = CandidateTable()
    initial_widths = [table.columnWidth(i) for i in range(table.columnCount())]
    table.load_candidates(
        [
            CandidateRecord(
                title="A very long candidate title that should not change header positions after reload",
                authors=["Author One", "Author Two"],
                year=2024,
                doi="10.1/candidate",
                source="crossref",
                score=0.93,
            )
        ]
    )
    reloaded_widths = [table.columnWidth(i) for i in range(table.columnCount())]
    assert reloaded_widths == initial_widths
