from __future__ import annotations

from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from bibtex_mvp.domain.models import CandidateRecord


def _configure_fixed_columns(table: QTableWidget, widths: list[int]) -> None:
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
    for index, width in enumerate(widths):
        table.setColumnWidth(index, width)


class CandidateTable(QTableWidget):
    def __init__(self) -> None:
        super().__init__(0, 6)
        self.setHorizontalHeaderLabels(["分数", "标题", "作者", "年份", "DOI", "来源"])
        _configure_fixed_columns(self, [80, 420, 220, 80, 170, 120])
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._records: list[CandidateRecord] = []

    def load_candidates(self, candidates: list[CandidateRecord]) -> None:
        self._records = candidates
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
        _configure_fixed_columns(self, [80, 420, 220, 80, 170, 180])
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._indexes: list[int] = []

    def load_rows(self, rows: list[dict]) -> None:
        self._indexes = [int(row["index"]) for row in rows]
        self.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self.setItem(row_index, 0, QTableWidgetItem(str(row["index"])))
            self.setItem(row_index, 1, QTableWidgetItem(str(row.get("title", ""))))
            self.setItem(row_index, 2, QTableWidgetItem(str(row.get("authors", ""))))
            self.setItem(row_index, 3, QTableWidgetItem(str(row.get("year", ""))))
            self.setItem(row_index, 4, QTableWidgetItem(str(row.get("doi", ""))))
            self.setItem(row_index, 5, QTableWidgetItem(str(row.get("message", ""))))
        self.clearSelection()

    def selected_index(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if row < 0 or row >= len(self._indexes):
            return None
        return self._indexes[row]
