"""Replaceable access contract for online spreadsheet operations."""

from collections.abc import Sequence
from typing import Protocol

from quiz_buzzer.sheets.models import CellUpdate, SpreadsheetStructure


class SheetsAdapter(Protocol):
    def read_structure(
        self, sheet_url: str, worksheet_id: str | None = None
    ) -> SpreadsheetStructure:
        """Read sheet structure, optionally restricted to a worksheet ID."""

    def write_answers(self, spreadsheet_id: str, updates: Sequence[CellUpdate]) -> None:
        """Write answer strings to the specified answer-cell coordinates."""
