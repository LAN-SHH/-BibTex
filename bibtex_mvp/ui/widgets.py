from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QSizePolicy, QTableWidget, QTableWidgetItem

from bibtex_mvp.domain.models import CandidateRecord

_RESULT_TABLE_WIDTHS = [74, 420, 220, 88, 180, 220]
_CANDIDATE_TABLE_WIDTHS = [84, 420, 220, 88, 180, 120]


def _apply_table_basics(table: QTableWidget, widths: list[int]) -> None:
    header = table.horizontalHeader()
    table.verticalHeader().setVisible(False)
    header.setStretchLastSection(False)
    header.setMinimumSectionSize(60)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    table.verticalScrollBar().setSingleStep(24)
    table.horizontalScrollBar().setSingleStep(24)
    table.setWordWrap(False)
    table.setShowGrid(False)
    table.setGridStyle(Qt.PenStyle.NoPen)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    for index, width in enumerate(widths):
        table.setColumnWidth(index, width)

    palette = table.palette()
    palette.setColor(QPalette.ColorRole.Base, QColor("#fbfcfe"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f2f6fb"))
    palette.setColor(QPalette.ColorRole.Window, QColor("#fbfcfe"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#102033"))
    table.setPalette(palette)
    table.viewport().setPalette(palette)

    table.setStyleSheet(
        """
        QTableWidget {
            background: #fbfcfe;
            color: #102033;
            border: 1px solid #d4ddea;
            border-radius: 12px;
            padding-bottom: 2px;
            alternate-background-color: #f2f6fb;
            selection-background-color: #dfe9f7;
            selection-color: #11223a;
        }
        QTableWidget::item {
            padding: 6px 8px;
            border-bottom: 1px solid #edf2f7;
        }
        QTableWidget::item:selected {
            background: #dfe9f7;
            color: #11223a;
        }
        QHeaderView::section {
            background: #edf3f9;
            color: #20324b;
            border: none;
            border-right: 1px solid #d8e1ec;
            border-bottom: 1px solid #d8e1ec;
            padding: 8px 8px;
            font-weight: 700;
        }
        QHeaderView::section:first {
            border-top-left-radius: 12px;
        }
        QScrollBar:vertical {
            background: transparent;
            width: 8px;
            margin: 4px 0 4px 0;
        }
        QScrollBar::handle:vertical {
            background: #cad6e7;
            min-height: 28px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background: #aebfd8;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical,
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal,
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {
            background: transparent;
            border: none;
        }
        QScrollBar:horizontal {
            background: transparent;
            height: 8px;
            margin: 0 4px 0 4px;
        }
        QScrollBar::handle:horizontal {
            background: #cad6e7;
            min-width: 28px;
            border-radius: 4px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #aebfd8;
        }
        """
    )


class CandidateTable(QTableWidget):
    def __init__(self) -> None:
        super().__init__(0, 6)
        self.setHorizontalHeaderLabels(["分数", "标题", "作者", "年份", "DOI", "来源"])
        _apply_table_basics(self, _CANDIDATE_TABLE_WIDTHS)
        self._records: list[CandidateRecord] = []

    def load_candidates(self, candidates: list[CandidateRecord]) -> None:
        self.setUpdatesEnabled(False)
        self._records = candidates
        self.clearContents()
        self.setRowCount(len(candidates))
        for row, candidate in enumerate(candidates):
            self.setItem(row, 0, QTableWidgetItem(f"{candidate.score:.3f}"))
            self.setItem(row, 1, QTableWidgetItem(candidate.title))
            self.setItem(row, 2, QTableWidgetItem(", ".join(candidate.authors)))
            self.setItem(row, 3, QTableWidgetItem(str(candidate.year or "")))
            self.setItem(row, 4, QTableWidgetItem(candidate.doi or ""))
            self.setItem(row, 5, QTableWidgetItem(candidate.source))
        if candidates:
            self.selectRow(0)
        else:
            self.clearSelection()
        self.setUpdatesEnabled(True)
        self.viewport().update()

    def selected_candidate(self) -> CandidateRecord | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        index = selected[0].row()
        if index < 0 or index >= len(self._records):
            return None
        return self._records[index]


class ResultTable(QTableWidget):
    def __init__(self) -> None:
        super().__init__(0, 6)
        self.setHorizontalHeaderLabels(["编号", "标题", "作者", "年份", "DOI", "说明"])
        _apply_table_basics(self, _RESULT_TABLE_WIDTHS)
        self._indexes: list[int] = []

    def load_rows(self, rows: list[dict]) -> None:
        self.setUpdatesEnabled(False)
        self._indexes = [int(row["index"]) for row in rows]
        self.clearContents()
        self.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self.setItem(row_index, 0, QTableWidgetItem(str(row["index"])))
            self.setItem(row_index, 1, QTableWidgetItem(str(row.get("title", ""))))
            self.setItem(row_index, 2, QTableWidgetItem(str(row.get("authors", ""))))
            self.setItem(row_index, 3, QTableWidgetItem(str(row.get("year", ""))))
            self.setItem(row_index, 4, QTableWidgetItem(str(row.get("doi", ""))))
            self.setItem(row_index, 5, QTableWidgetItem(str(row.get("message", ""))))
        self.clearSelection()
        self.setUpdatesEnabled(True)
        self.viewport().update()

    def selected_index(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if row < 0 or row >= len(self._indexes):
            return None
        return self._indexes[row]
