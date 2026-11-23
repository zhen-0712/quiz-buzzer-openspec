from pathlib import Path

import pytest

from quiz_buzzer.sheets.models import MergedRange, SpreadsheetStructure, WorksheetGrid
from quiz_buzzer.sheets.parser import SheetParseError, parse_guided_notes
from tests.fakes import MemorySheetsAdapter
from tests.workbook_fixtures import load_xlsx_as_sheet_structure


FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.parametrize(
    ("filename_part", "expected_numbers", "expected_blank_counts"),
    [
        ("單題", ["1", "2", "3", "4", "5", "6"], [1, 1, 1, 1, 1, 1]),
        ("題組", ["1", "2", "3", "4"], [2, 2, 1, 1]),
    ],
)
def test_parser_reads_supplied_workbook_template_via_fake_adapter(
    filename_part, expected_numbers, expected_blank_counts
):
    matching = [path for path in FIXTURES.glob("*.xlsx") if filename_part in path.name]
    assert len(matching) == 1
    url = f"fake://fixtures/{matching[0].name}"
    adapter = MemorySheetsAdapter(
        {url: load_xlsx_as_sheet_structure(matching[0])}
    )

    structure = adapter.read_structure(url)
    parsed = parse_guided_notes(structure)

    assert adapter.read_calls == [url]
    assert [question.question_number for question in parsed.questions] == expected_numbers
    assert [len(question.blanks) for question in parsed.questions] == expected_blank_counts
    assert parsed.worksheet_title == "學習單"
    assert parsed.header_row_index == 3
    assert parsed.question_column_index == 1
    assert parsed.answer_column_index == 6


def test_fixture_snapshot_preserves_question_blank_order_and_cell_coordinates():
    fixture = next(path for path in FIXTURES.glob("*.xlsx") if "題組" in path.name)
    parsed = parse_guided_notes(load_xlsx_as_sheet_structure(fixture))

    snapshot = parsed.structure_snapshot()

    assert [question["question_number"] for question in snapshot["questions"]] == [
        "1",
        "2",
        "3",
        "4",
    ]
    assert [blank["a1_address"] for blank in snapshot["questions"][0]["blanks"]] == [
        "G5",
        "G6",
    ]
    assert [blank["position"] for blank in snapshot["questions"][0]["blanks"]] == [0, 1]
    assert snapshot["questions"][0]["position"] == 0
    assert snapshot["worksheet_id"] == "1"


def test_parser_finds_shifted_headers_and_mixed_single_and_group_questions():
    structure = SpreadsheetStructure(
        spreadsheet_id="shifted",
        worksheets=[
            WorksheetGrid(
                worksheet_id="12",
                title="Shifted",
                values=[
                    [None] * 5,
                    [None] * 5,
                    [None] * 5,
                    [None] * 5,
                    [None, None, "題號", None, "作答"],
                    [None, None, "A", None, None],
                    [None, None, "B", None, None],
                    [None, None, None, None, None],
                    [None, None, "C", None, None],
                ],
                merged_ranges=[MergedRange(6, 8, 2, 3)],
            )
        ],
    )

    parsed = parse_guided_notes(structure)

    assert parsed.header_row_index == 4
    assert parsed.question_column_index == 2
    assert parsed.answer_column_index == 4
    assert [question.question_number for question in parsed.questions] == ["A", "B", "C"]
    assert [len(question.blanks) for question in parsed.questions] == [1, 2, 1]
    assert parsed.questions[1].blanks[0].a1_address == "E7"
    assert parsed.questions[1].blanks[1].a1_address == "E8"


@pytest.mark.parametrize(
    ("values", "expected_location"),
    [
        ([['題號', '題號', '作答'], ['1', None, None]], "B1"),
        ([['題號', '題目'], ['1', 'description']], "A1"),
        ([['題目', '作答'], ['description', None]], "B1"),
    ],
)
def test_parser_reports_duplicate_or_missing_headers(values, expected_location):
    worksheet = WorksheetGrid("11", "Bad headers", values)

    with pytest.raises(SheetParseError) as error:
        parse_guided_notes(SpreadsheetStructure("bad-headers", [worksheet]))

    assert error.value.worksheet_title == "Bad headers"
    assert error.value.location == expected_location
    assert "工作表「Bad headers」" in str(error.value)


def test_parser_reports_question_number_that_cannot_be_uniquely_assigned():
    worksheet = WorksheetGrid(
        "5",
        "Ambiguous number",
        [["題號", "題目", "作答"], ["1", "first", None], [None, "unassigned row", None]],
    )

    with pytest.raises(SheetParseError, match="無法唯一歸屬題號") as error:
        parse_guided_notes(SpreadsheetStructure("ambiguous", [worksheet]))

    assert error.value.location == "A3"


def test_parser_requires_one_unique_header_row_and_nonempty_question_set():
    duplicate_header_rows = WorksheetGrid(
        "1",
        "Two headers",
        [["題號", "作答"], ["1", None], ["題號", "作答"], ["2", None]],
    )
    with pytest.raises(SheetParseError, match="多個可能"):
        parse_guided_notes(SpreadsheetStructure("two-headers", [duplicate_header_rows]))

    no_questions = WorksheetGrid("1", "Empty", [["題號", "作答"], [None, None]])
    with pytest.raises(SheetParseError, match="沒有可匯入的題目"):
        parse_guided_notes(SpreadsheetStructure("empty", [no_questions]))
