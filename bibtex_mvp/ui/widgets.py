from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from bibtex_mvp.domain.models import CandidateRecord


class CandidateTable(QTableWidget):
    def __init__(self) -> None:
        super().__init__(0, 6)
        self.setHorizontalHeaderLabels(["分数", "标题", "作者", "年份", "DOI", "来源"])
        self.horizontalHeader().setStretchLastSection(True)
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
        self.resizeColumnsToContents()
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
