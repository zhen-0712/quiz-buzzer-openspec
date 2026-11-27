"""Convert supplied xlsx templates into transport-neutral fake Sheet data."""

from pathlib import Path

from openpyxl import load_workbook

from quiz_buzzer.sheets.models import MergedRange, SpreadsheetStructure, WorksheetGrid


def load_xlsx_as_sheet_structure(path: Path) -> SpreadsheetStructure:
    workbook = load_workbook(path, data_only=True, read_only=False)
    try:
        worksheets = []
        for index, worksheet in enumerate(workbook.worksheets, start=1):
            values = [
                [_formatted_value(cell.value) for cell in row]
                for row in worksheet.iter_rows(
                    min_row=1,
                    max_row=worksheet.max_row,
                    min_col=1,
                    max_col=worksheet.max_column,
                )
            ]
            merged_ranges = [
                MergedRange(
                    start_row_index=merged.min_row - 1,
                    end_row_index=merged.max_row,
                    start_column_index=merged.min_col - 1,
                    end_column_index=merged.max_col,
                )
                for merged in worksheet.merged_cells.ranges
            ]
            worksheets.append(
                WorksheetGrid(
                    worksheet_id=str(index),
                    title=worksheet.title,
                    values=values,
                    merged_ranges=merged_ranges,
                )
            )
        return SpreadsheetStructure(
            spreadsheet_id=f"fixture-{path.stem}", worksheets=worksheets
        )
    finally:
        workbook.close()


def _formatted_value(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
