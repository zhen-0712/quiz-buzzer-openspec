"""Print question and answer-cell summaries for local Guided Notes xlsx files."""

from pathlib import Path

from quiz_buzzer.sheets.parser import parse_guided_notes
from tests.workbook_fixtures import load_xlsx_as_sheet_structure


def main() -> None:
    fixtures_dir = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    workbooks = sorted(fixtures_dir.glob("*.xlsx"))
    if not workbooks:
        raise SystemExit(f"找不到範本檔：{fixtures_dir}")

    for workbook_path in workbooks:
        parsed = parse_guided_notes(load_xlsx_as_sheet_structure(workbook_path))
        print(f"{workbook_path.name}（工作表：{parsed.worksheet_title}）")
        print(f"題數：{len(parsed.questions)}")
        for question in parsed.questions:
            coordinates = ", ".join(blank.a1_address for blank in question.blanks)
            print(
                f"  題號 {question.question_number}："
                f"{len(question.blanks)} 個填空；座標：{coordinates}"
            )


if __name__ == "__main__":
    main()
