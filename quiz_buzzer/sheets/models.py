"""Transport-neutral worksheet structures used by parsers and adapters."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MergedRange:
    start_row_index: int
    end_row_index: int
    start_column_index: int
    end_column_index: int


@dataclass
class WorksheetGrid:
    worksheet_id: str
    title: str
    values: list[list[Any]] = field(default_factory=list)
    merged_ranges: list[MergedRange] = field(default_factory=list)


@dataclass
class SpreadsheetStructure:
    spreadsheet_id: str
    worksheets: list[WorksheetGrid] = field(default_factory=list)


@dataclass(frozen=True)
class CellUpdate:
    worksheet_id: str
    row_index: int
    column_index: int
    value: str


class SheetsAdapterError(RuntimeError):
    """A read/write failure from a configured Sheets implementation."""
