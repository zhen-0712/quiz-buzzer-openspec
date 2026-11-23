"""Offline test doubles for the replaceable Google Sheets adapter."""

from collections.abc import Sequence

from quiz_buzzer.sheets.models import CellUpdate, SpreadsheetStructure


class MemorySheetsAdapter:
    def __init__(self, sources: dict[str, SpreadsheetStructure] | None = None):
        self.sources = dict(sources or {})
        self.read_calls: list[str] = []
        self.write_calls: list[tuple[str, list[CellUpdate]]] = []

    def register(self, sheet_url: str, structure: SpreadsheetStructure) -> None:
        self.sources[sheet_url] = structure

    def read_structure(self, sheet_url: str) -> SpreadsheetStructure:
        self.read_calls.append(sheet_url)
        try:
            return self.sources[sheet_url]
        except KeyError as error:
            raise RuntimeError("fake sheet is not registered") from error

    def write_answers(self, spreadsheet_id: str, updates: Sequence[CellUpdate]) -> None:
        self.write_calls.append((spreadsheet_id, list(updates)))
