"""Dynamic Guided Notes question and answer-cell parser."""

from dataclasses import dataclass
from typing import Any

from quiz_buzzer.sheets.models import MergedRange, SpreadsheetStructure, WorksheetGrid


@dataclass(frozen=True)
class ParsedBlank:
    position: int
    worksheet_id: str
    row_index: int
    column_index: int
    a1_address: str


@dataclass(frozen=True)
class ParsedQuestion:
    position: int
    question_number: str
    blanks: tuple[ParsedBlank, ...]


@dataclass(frozen=True)
class ParsedGuidedNotes:
    spreadsheet_id: str
    worksheet_id: str
    worksheet_title: str
    header_row_index: int
    question_column_index: int
    answer_column_index: int
    questions: tuple[ParsedQuestion, ...]

    def structure_snapshot(self) -> dict[str, Any]:
        return {
            "spreadsheet_id": self.spreadsheet_id,
            "worksheet_id": self.worksheet_id,
            "worksheet_title": self.worksheet_title,
            "header_row_index": self.header_row_index,
            "question_column_index": self.question_column_index,
            "answer_column_index": self.answer_column_index,
            "questions": [
                {
                    "position": question.position,
                    "question_number": question.question_number,
                    "blanks": [
                        {
                            "position": blank.position,
                            "row_index": blank.row_index,
                            "column_index": blank.column_index,
                            "a1_address": blank.a1_address,
                        }
                        for blank in question.blanks
                    ],
                }
                for question in self.questions
            ],
        }


class SheetParseError(ValueError):
    def __init__(self, worksheet_title: str, location: str, reason: str):
        self.worksheet_title = worksheet_title
        self.location = location
        self.reason = reason
        super().__init__(f"工作表「{worksheet_title}」{location}：{reason}")


def parse_guided_notes(structure: SpreadsheetStructure) -> ParsedGuidedNotes:
    candidates: list[tuple[WorksheetGrid, int, int, int]] = []
    partial_headers: list[tuple[WorksheetGrid, int, int, str]] = []

    for worksheet in structure.worksheets:
        for row_index, row in enumerate(worksheet.values):
            question_columns = [i for i, value in enumerate(row) if _header_text(value) == "題號"]
            answer_columns = [i for i, value in enumerate(row) if _header_text(value) == "作答"]
            if len(question_columns) > 1:
                raise SheetParseError(
                    worksheet.title,
                    _a1(row_index, question_columns[1]),
                    "「題號」標題重複，無法唯一判讀",
                )
            if len(answer_columns) > 1:
                raise SheetParseError(
                    worksheet.title,
                    _a1(row_index, answer_columns[1]),
                    "「作答」標題重複，無法唯一判讀",
                )
            if question_columns and answer_columns:
                candidates.append(
                    (worksheet, row_index, question_columns[0], answer_columns[0])
                )
            elif question_columns:
                partial_headers.append(
                    (worksheet, row_index, question_columns[0], "找不到同列的「作答」標題")
                )
            elif answer_columns:
                partial_headers.append(
                    (worksheet, row_index, answer_columns[0], "找不到同列的「題號」標題")
                )

    if len(candidates) > 1:
        worksheet, row_index, question_column, _answer_column = candidates[1]
        raise SheetParseError(
            worksheet.title,
            _a1(row_index, question_column),
            "找到多個可能的「題號／作答」標題列，無法唯一判讀",
        )
    if not candidates:
        if partial_headers:
            worksheet, row_index, column_index, reason = partial_headers[0]
            raise SheetParseError(worksheet.title, _a1(row_index, column_index), reason)
        worksheet_title = structure.worksheets[0].title if structure.worksheets else "（無工作表）"
        raise SheetParseError(worksheet_title, "標題列", "找不到「題號」與「作答」標題")

    worksheet, header_row, question_column, answer_column = candidates[0]
    questions = _parse_question_rows(
        worksheet, header_row, question_column, answer_column
    )
    if not questions:
        raise SheetParseError(worksheet.title, _a1(header_row + 1, question_column), "沒有可匯入的題目")
    return ParsedGuidedNotes(
        spreadsheet_id=structure.spreadsheet_id,
        worksheet_id=worksheet.worksheet_id,
        worksheet_title=worksheet.title,
        header_row_index=header_row,
        question_column_index=question_column,
        answer_column_index=answer_column,
        questions=tuple(questions),
    )


def _parse_question_rows(
    worksheet: WorksheetGrid, header_row: int, question_column: int, answer_column: int
) -> list[ParsedQuestion]:
    last_row = max(
        len(worksheet.values),
        max((merged.end_row_index for merged in worksheet.merged_ranges), default=0),
    )
    questions: dict[str, list[ParsedBlank]] = {}
    question_order: list[str] = []
    answer_anchor_owner: dict[tuple[int, int], str] = {}

    for row_index in range(header_row + 1, last_row):
        question_value = _cell_value(worksheet, row_index, question_column)
        question_merge = _question_merge_at(
            worksheet.merged_ranges, row_index, question_column
        )
        if question_merge is not None:
            question_value = _cell_value(
                worksheet,
                question_merge.start_row_index,
                question_merge.start_column_index,
            )
        question_number = _question_number(question_value)

        if not question_number:
            if question_merge is not None:
                raise SheetParseError(
                    worksheet.title,
                    _a1(question_merge.start_row_index, question_merge.start_column_index),
                    "合併題號儲存格沒有題號",
                )
            if _row_has_data(worksheet, row_index):
                raise SheetParseError(
                    worksheet.title,
                    _a1(row_index, question_column),
                    "此資料列無法唯一歸屬題號（題號空白且未合併）",
                )
            continue

        if question_number not in questions:
            questions[question_number] = []
            question_order.append(question_number)

        answer_merge = _merged_range_at(
            worksheet.merged_ranges, row_index, answer_column
        )
        answer_row = answer_merge.start_row_index if answer_merge else row_index
        answer_col = answer_merge.start_column_index if answer_merge else answer_column
        answer_anchor = (answer_row, answer_col)
        previous_owner = answer_anchor_owner.get(answer_anchor)
        if previous_owner is not None and previous_owner != question_number:
            raise SheetParseError(
                worksheet.title,
                _a1(answer_row, answer_col),
                "同一作答格同時對應多個題號，無法唯一判讀",
            )
        answer_anchor_owner[answer_anchor] = question_number

        if not any(
            blank.row_index == answer_row and blank.column_index == answer_col
            for blank in questions[question_number]
        ):
            questions[question_number].append(
                ParsedBlank(
                    position=len(questions[question_number]),
                    worksheet_id=worksheet.worksheet_id,
                    row_index=answer_row,
                    column_index=answer_col,
                    a1_address=_a1(answer_row, answer_col),
                )
            )

    return [
        ParsedQuestion(position=index, question_number=number, blanks=tuple(questions[number]))
        for index, number in enumerate(question_order)
    ]


def _header_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _question_number(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        numeric = float(value)
        return str(int(numeric)) if numeric.is_integer() else str(value)
    return str(value).strip()


def _cell_value(worksheet: WorksheetGrid, row: int, column: int) -> Any:
    if row < 0 or column < 0 or row >= len(worksheet.values):
        return None
    values = worksheet.values[row]
    return values[column] if column < len(values) else None


def _row_has_data(worksheet: WorksheetGrid, row: int) -> bool:
    if row < 0 or row >= len(worksheet.values):
        return False
    return any(value is not None and str(value).strip() for value in worksheet.values[row])


def _merged_range_at(
    merged_ranges: list[MergedRange], row: int, column: int
) -> MergedRange | None:
    for merged in merged_ranges:
        if (
            merged.start_row_index <= row < merged.end_row_index
            and merged.start_column_index <= column < merged.end_column_index
        ):
            return merged
    return None


def _question_merge_at(
    merged_ranges: list[MergedRange], row: int, question_column: int
) -> MergedRange | None:
    for merged in merged_ranges:
        if (
            merged.start_row_index <= row < merged.end_row_index
            and merged.start_column_index == question_column
            and merged.end_column_index == question_column + 1
            and merged.end_row_index - merged.start_row_index > 1
        ):
            return merged
    return None


def _a1(row_index: int, column_index: int) -> str:
    value = column_index + 1
    letters = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row_index + 1}"
