"""Offline test doubles for the replaceable Google Sheets adapter."""

from collections.abc import Sequence
from quiz_buzzer.sheets.models import CellUpdate, SpreadsheetStructure


class MemorySheetsAdapter:
    def __init__(self, sources: dict[str, SpreadsheetStructure] | None = None):
        self.sources = dict(sources or {})
        self.read_calls: list[str] = []
        self.worksheet_read_calls: list[tuple[str, str | None]] = []
        self.write_calls: list[tuple[str, list[CellUpdate]]] = []

    def register(self, sheet_url: str, structure: SpreadsheetStructure) -> None:
        self.sources[sheet_url] = structure

    def read_structure(
        self, sheet_url: str, worksheet_id: str | None = None
    ) -> SpreadsheetStructure:
        self.read_calls.append(sheet_url)
        self.worksheet_read_calls.append((sheet_url, worksheet_id))
        try:
            structure = self.sources[sheet_url]
        except KeyError as error:
            raise RuntimeError("fake sheet is not registered") from error
        if worksheet_id is None:
            return structure
        worksheets = [
            worksheet
            for worksheet in structure.worksheets
            if worksheet.worksheet_id == str(worksheet_id)
        ]
        if not worksheets:
            raise RuntimeError(f"fake worksheet not found: {worksheet_id}")
        return SpreadsheetStructure(structure.spreadsheet_id, worksheets)

    def write_answers(self, spreadsheet_id: str, updates: Sequence[CellUpdate]) -> None:
        self.write_calls.append((spreadsheet_id, list(updates)))
