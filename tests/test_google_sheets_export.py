import copy
import csv
import io
from pathlib import Path

import pytest

from quiz_buzzer import create_app
from quiz_buzzer.data.database import get_db
from quiz_buzzer.sheets.google_adapter import GoogleSheetsAdapter
from quiz_buzzer.sheets.models import MergedRange, SheetsAdapterError, WorksheetGrid
from tests.fakes import MemorySheetsAdapter
from tests.workbook_fixtures import load_xlsx_as_sheet_structure


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "軟工期末專案_題組_範例.xlsx"
SHEET_URL = "https://docs.google.com/spreadsheets/d/fake-export-sheet/edit"


class FailingWriteAdapter(MemorySheetsAdapter):
    def write_answers(self, spreadsheet_id, updates):
        self.write_calls.append((spreadsheet_id, list(updates)))
        raise RuntimeError("fake write failure")


class FailingReadAdapter(MemorySheetsAdapter):
    def read_structure(self, sheet_url, worksheet_id=None):
        self.read_calls.append(sheet_url)
        self.worksheet_read_calls.append((sheet_url, worksheet_id))
        raise RuntimeError("fake read failure")


class SnapshotFieldMutationAdapter(MemorySheetsAdapter):
    def __init__(self, sources, mutation):
        super().__init__(sources)
        self.mutation = mutation

    def read_structure(self, sheet_url, worksheet_id=None):
        structure = super().read_structure(sheet_url, worksheet_id)
        changed = copy.deepcopy(structure)
        worksheet = changed.worksheets[0]
        if self.mutation == "worksheet_id":
            worksheet.worksheet_id = "changed-worksheet-id"
        elif self.mutation == "worksheet_title":
            worksheet.title = "Changed worksheet title"
        elif self.mutation == "header_row_index":
            worksheet.values.insert(0, [])
            worksheet.merged_ranges = [
                MergedRange(
                    item.start_row_index + 1,
                    item.end_row_index + 1,
                    item.start_column_index,
                    item.end_column_index,
                )
                for item in worksheet.merged_ranges
            ]
        elif self.mutation in {"question_column_index", "answer_column_index"}:
            header_row = next(
                row for row in worksheet.values
                if "題號" in row and "作答" in row
            )
            start_column = 0 if self.mutation == "question_column_index" else header_row.index("作答")
            for row in worksheet.values:
                row.insert(start_column, None)
            worksheet.merged_ranges = [
                MergedRange(
                    item.start_row_index,
                    item.end_row_index,
                    item.start_column_index + (item.start_column_index >= start_column),
                    item.end_column_index + (item.end_column_index > start_column),
                )
                for item in worksheet.merged_ranges
            ]
        return changed


@pytest.fixture
def app(tmp_path):
    structure = load_xlsx_as_sheet_structure(FIXTURE)
    adapter = MemorySheetsAdapter({SHEET_URL: structure})
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "export-test-session-key",
            "DATABASE": str(tmp_path / "export.sqlite3"),
            "SHEETS_ADAPTER": adapter,
        }
    )
    return application


def _setup(app, *, import_sheet=True, phase="preparation"):
    teacher = app.test_client()
    created = teacher.post(
        "/api/activities", json={"group_count": 2, "password": "teacher pass"}
    ).get_json()
    code = created["activity_code"]
    group_a = app.test_client()
    group_b = app.test_client()
    group_a.post(f"/api/activities/{code}/join", json={"group_number": 1})
    group_b.post(f"/api/activities/{code}/join", json={"group_number": 2})
    adapter = app.config["SHEETS_ADAPTER"]
    if import_sheet:
        imported = teacher.post(
            f"/api/activities/{code}/import", json={"sheet_url": SHEET_URL}
        )
        assert imported.status_code == 200
    if phase in {"active", "ended"}:
        started = teacher.post(f"/api/activities/{code}/phase", json={"phase": "active"})
        assert started.status_code == 200
    if phase == "ended":
        ended = teacher.post(f"/api/activities/{code}/phase", json={"phase": "ended"})
        assert ended.status_code == 200
    return code, teacher, group_a, group_b, adapter


def _submit(client, code, question_number, answers):
    return client.post(
        f"/api/activities/{code}/submissions",
        json={"question_number": question_number, "answers": answers},
    )


def _export(client, code, confirm_backup=True):
    return client.post(
        f"/api/activities/{code}/export",
        json={"confirm_backup": confirm_backup},
    )


def _mutate_source(structure, mutation):
    changed = copy.deepcopy(structure)
    worksheet = changed.worksheets[0]
    if mutation == "source":
        changed.spreadsheet_id = "different-source-id"
    elif mutation == "question_number":
        worksheet.values[4][1] = "Q1"
    elif mutation == "blank_count":
        worksheet.merged_ranges = [
            merge
            for merge in worksheet.merged_ranges
            if not (
                merge.start_row_index == 4
                and merge.end_row_index == 5
                and merge.start_column_index == 6
                and merge.end_column_index == 8
            )
        ]
        worksheet.merged_ranges.append(MergedRange(4, 6, 6, 7))
    elif mutation == "question_order":
        worksheet.values[4][1], worksheet.values[7][1] = (
            worksheet.values[7][1],
            worksheet.values[4][1],
        )
    elif mutation == "position":
        worksheet.values = [row[:6] + [None] + row[6:] for row in worksheet.values]
        worksheet.merged_ranges = [
            MergedRange(
                merge.start_row_index,
                merge.end_row_index,
                merge.start_column_index + (merge.start_column_index >= 6),
                merge.end_column_index + (merge.end_column_index > 6),
            )
            for merge in worksheet.merged_ranges
        ]
    return changed


def test_export_requires_ended_phase_and_explicit_backup_confirmation(app):
    code, teacher, _group_a, _group_b, adapter = _setup(app)
    adapter.read_calls.clear()

    not_ended = _export(teacher, code)
    assert not_ended.status_code == 409
    assert not_ended.get_json()["error"] == "export_phase_closed"
    assert adapter.read_calls == []
    assert adapter.write_calls == []

    imported = teacher.post(
        f"/api/activities/{code}/import", json={"sheet_url": SHEET_URL}
    )
    assert imported.status_code == 200
    adapter.read_calls.clear()
    teacher.post(f"/api/activities/{code}/phase", json={"phase": "active"})
    teacher.post(f"/api/activities/{code}/phase", json={"phase": "ended"})
    adapter.read_calls.clear()

    unconfirmed = _export(teacher, code, confirm_backup=False)

    assert unconfirmed.status_code == 400
    assert unconfirmed.get_json()["error"] == "backup_confirmation_required"
    assert "備份" in unconfirmed.get_json()["message"]
    assert adapter.read_calls == []
    assert adapter.write_calls == []


def test_export_reparses_snapshot_and_writes_only_winners_in_blank_order_repeatedly(app):
    code, teacher, group_a, group_b, adapter = _setup(app, phase="active")
    _submit(group_a, code, "1", ["A 初答 1", "A 初答 2"])
    _submit(group_b, code, "1", ["B 勝出 1", "B 勝出 2"])
    _submit(group_a, code, "1", ["A 重送 1", "A 重送 2"])
    _submit(group_a, code, "3", ["單題中文答案"])
    teacher.post(f"/api/activities/{code}/phase", json={"phase": "ended"})
    adapter.read_calls.clear()

    response = _export(teacher, code)
    repeated = _export(teacher, code)

    assert response.status_code == repeated.status_code == 200
    assert response.get_json() == {
        "status": "success",
        "questions_written": 2,
        "cells_written": 3,
    }
    assert len(adapter.read_calls) == 2
    assert len(adapter.write_calls) == 2
    spreadsheet_id, updates = adapter.write_calls[0]
    expected = load_xlsx_as_sheet_structure(FIXTURE)
    from quiz_buzzer.sheets.parser import parse_guided_notes

    parsed = parse_guided_notes(expected)
    q1, q3 = parsed.questions[0], parsed.questions[2]
    assert spreadsheet_id == expected.spreadsheet_id
    assert [(item.row_index, item.column_index, item.value) for item in updates] == [
        (q1.blanks[0].row_index, q1.blanks[0].column_index, "B 勝出 1"),
        (q1.blanks[1].row_index, q1.blanks[1].column_index, "B 勝出 2"),
        (q3.blanks[0].row_index, q3.blanks[0].column_index, "單題中文答案"),
    ]
    assert adapter.write_calls[1] == adapter.write_calls[0]


def test_export_rechecks_only_the_worksheet_recorded_at_import(app):
    code, teacher, _group_a, _group_b, adapter = _setup(app, phase="ended")
    structure = adapter.sources[SHEET_URL]
    imported_worksheet_id = structure.worksheets[0].worksheet_id
    structure.worksheets.append(
        WorksheetGrid("999", "Later matching sheet", [["題號", "作答"], ["9", None]])
    )

    response = _export(teacher, code)

    assert response.status_code == 200
    assert adapter.worksheet_read_calls[-1] == (SHEET_URL, imported_worksheet_id)
    assert adapter.write_calls == []


def test_export_aborts_when_recorded_worksheet_is_missing_without_fallback(app):
    code, teacher, _group_a, _group_b, adapter = _setup(app, phase="ended")
    structure = adapter.sources[SHEET_URL]
    structure.worksheets.append(
        WorksheetGrid("999", "Fallback candidate", [["題號", "作答"], ["9", None]])
    )
    structure.worksheets[:] = [worksheet for worksheet in structure.worksheets if worksheet.worksheet_id != "1"]

    response = _export(teacher, code)

    assert response.status_code == 502
    assert "fake worksheet not found: 1" in response.get_json()["message"]
    assert adapter.write_calls == []


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("source", "來源識別碼"),
        ("question_number", "題號"),
        ("blank_count", "填空數"),
        ("question_order", "題目順序"),
        ("position", "位置"),
    ],
)
def test_export_structure_differences_abort_before_any_write(app, mutation, reason):
    code, teacher, _group_a, _group_b, adapter = _setup(app, phase="ended")
    adapter.sources[SHEET_URL] = _mutate_source(adapter.sources[SHEET_URL], mutation)
    adapter.read_calls.clear()

    response = _export(teacher, code)

    assert response.status_code == 409
    assert response.get_json()["error"] == "export_structure_changed"
    assert reason in response.get_json()["message"]
    assert adapter.read_calls == [SHEET_URL]
    assert adapter.write_calls == []


def test_export_collects_every_affected_question_before_zero_write(app):
    code, teacher, _group_a, _group_b, adapter = _setup(app, phase="ended")
    changed = _mutate_source(adapter.sources[SHEET_URL], "question_number")
    changed = _mutate_source(changed, "position")
    adapter.sources[SHEET_URL] = changed

    response = _export(teacher, code)

    assert response.status_code == 409
    message = response.get_json()["message"]
    assert "第 1 題" in message
    assert "第 Q1 題" in message
    assert "第 2 題" in message
    assert "第 3 題" in message
    assert "第 4 題" in message
    assert adapter.write_calls == []


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("worksheet_id", "工作表識別碼"),
        ("worksheet_title", "工作表名稱"),
        ("header_row_index", "標題列位置"),
        ("question_column_index", "題號欄位置"),
        ("answer_column_index", "作答欄位置"),
    ],
)
def test_export_aborts_on_each_worksheet_snapshot_field_change(app, mutation, reason):
    code, teacher, _group_a, _group_b, original_adapter = _setup(app, phase="ended")
    adapter = SnapshotFieldMutationAdapter(original_adapter.sources, mutation)
    app.config["SHEETS_ADAPTER"] = adapter

    response = _export(teacher, code)

    assert response.status_code == 409
    assert response.get_json()["error"] == "export_structure_changed"
    assert reason in response.get_json()["message"]
    assert adapter.write_calls == []


def test_export_aborts_when_local_answer_cell_count_disagrees_with_sheet(app):
    code, teacher, _group_a, _group_b, adapter = _setup(app, phase="ended")
    with app.app_context():
        database = get_db()
        question = database.execute(
            "SELECT id FROM questions WHERE question_number = '2'"
        ).fetchone()
        database.execute(
            "DELETE FROM answer_cells WHERE question_id = ? AND position = ("
            "SELECT MAX(position) FROM answer_cells WHERE question_id = ?)",
            (question["id"], question["id"]),
        )
        database.commit()

    response = _export(teacher, code)

    assert response.status_code == 409
    assert response.get_json()["error"] == "export_structure_changed"
    assert "第 2 題" in response.get_json()["message"]
    assert "本機填空格數" in response.get_json()["message"]
    assert adapter.write_calls == []


def test_export_read_failure_aborts_and_reports_reason(app):
    code, teacher, _group_a, _group_b, _adapter = _setup(app, phase="ended")
    failing_adapter = FailingReadAdapter()
    app.config["SHEETS_ADAPTER"] = failing_adapter

    response = _export(teacher, code)

    assert response.status_code == 502
    assert response.get_json()["error"] == "export_read_failed"
    assert "fake read failure" in response.get_json()["message"]
    assert failing_adapter.write_calls == []


def test_export_write_failure_is_reported_as_failure_not_success(app):
    code, teacher, group_a, _group_b, _adapter = _setup(app, phase="active")
    _submit(group_a, code, "3", ["answer"])
    teacher.post(f"/api/activities/{code}/phase", json={"phase": "ended"})
    failing_adapter = FailingWriteAdapter({SHEET_URL: load_xlsx_as_sheet_structure(FIXTURE)})
    app.config["SHEETS_ADAPTER"] = failing_adapter

    response = _export(teacher, code)

    assert response.status_code == 502
    assert response.get_json()["error"] == "export_write_failed"
    assert "fake write failure" in response.get_json()["message"]
    assert response.get_json().get("status") != "success"


def test_csv_is_winner_only_utf8_bom_crlf_and_one_row_per_blank(app):
    code, teacher, group_a, group_b, _adapter = _setup(app, phase="active")
    answers = ["逗號,答案", '引號"和換行\n第二行']
    _submit(group_a, code, "1", answers)
    _submit(group_b, code, "1", ["落敗答案一", "落敗答案二"])
    teacher.post(f"/api/activities/{code}/phase", json={"phase": "ended"})

    response = teacher.get(f"/api/activities/{code}/export.csv")

    assert response.status_code == 200
    assert response.data.startswith(b"\xef\xbb\xbf")
    assert "text/csv" in response.content_type
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert rows == [
        ["題號", "組別", "填空序號", "答案", "搶答順位"],
        ["1", "1", "1", answers[0], "1"],
        ["1", "1", "2", answers[1], "1"],
    ]
    assert b"\r\n" in response.data


def test_csv_matches_joy_safety_fixture_exact_bytes(app):
    import json
    from quiz_buzzer.sheets.models import SpreadsheetStructure, WorksheetGrid

    code, teacher, group, _group_b, adapter = _setup(app, import_sheet=False)
    answers_path = ROOT / "tests" / "fixtures" / "csv_joy_answers.json"
    entries = json.loads(answers_path.read_text(encoding="utf-8"))
    url = "fake://joy-csv"
    rows = [["題號", "作答"]]
    for entry in entries:
        rows.append([entry["question_number"], None])
    adapter.register(url, SpreadsheetStructure("joy-csv", [WorksheetGrid("77", "Joy", rows)]))
    assert teacher.post(f"/api/activities/{code}/import", json={"sheet_url": url}).status_code == 200
    assert teacher.post(f"/api/activities/{code}/phase", json={"phase": "active"}).status_code == 200
    for entry in entries:
        _submit(group, code, entry["question_number"], entry["answers"])
    assert teacher.post(f"/api/activities/{code}/phase", json={"phase": "ended"}).status_code == 200

    response = teacher.get(f"/api/activities/{code}/export.csv")
    expected = (
        "\ufeff題號,組別,填空序號,答案,搶答順位\r\n"
        '1,1,1,"\'=SUM(1,2)",1\r\n'
        "2,1,1,'+1,1\r\n"
        "3,1,1,'-1,1\r\n"
        "4,1,1,'@a,1\r\n"
        '5,1,1,"含逗號,和""雙引號""",1\r\n'
    ).encode("utf-8")
    assert response.data == expected
    sheet_export = _export(teacher, code)
    assert sheet_export.status_code == 200
    assert [update.value for _spreadsheet_id, updates in adapter.write_calls for update in updates] == [
        entry["answers"][0] for entry in entries
    ]


def test_csv_prefixes_control_characters_and_keeps_sheet_answers_unchanged(app):
    import json
    from quiz_buzzer.sheets.models import SpreadsheetStructure, WorksheetGrid

    code, teacher, group, _group_b, adapter = _setup(app, import_sheet=False)
    values = [
        {"question_number": "6", "answers": ["Tab"]},
        {"question_number": "7", "answers": ["CR", "LF"]},
        {"question_number": "8", "answers": ["第一格", "第二格"]},
    ]
    url = "fake://csv-control-prefixes"
    rows = [["題號", "作答"]]
    for item in values:
        for answer_index, _ in enumerate(item["answers"]):
            rows.append([item["question_number"], None])
    adapter.register(url, SpreadsheetStructure("csv-control", [WorksheetGrid("88", "CSV", rows)]))
    assert teacher.post(f"/api/activities/{code}/import", json={"sheet_url": url}).status_code == 200
    assert teacher.post(f"/api/activities/{code}/phase", json={"phase": "active"}).status_code == 200
    for item in values:
        _submit(group, code, item["question_number"], item["answers"])
    # Seed values that can exist in stored legacy/imported records to exercise CSV safety
    # for control-character prefixes that the current submission UI trims on input.
    with app.app_context():
        database = get_db()
        for question_number, position, raw_answer in (
            ("6", 0, "\tTab"),
            ("7", 0, "\rCR"),
            ("7", 1, "\nLF"),
        ):
            database.execute(
                "UPDATE submission_answers SET answer = ? WHERE submission_id = ("
                "SELECT s.id FROM submissions s JOIN questions q ON q.id = s.question_id "
                "JOIN groups g ON g.id = s.group_id WHERE q.question_number = ? "
                "AND g.group_number = 1 ORDER BY s.id DESC LIMIT 1) AND position = ?",
                (raw_answer, question_number, position),
            )
        database.commit()
    assert teacher.post(f"/api/activities/{code}/phase", json={"phase": "ended"}).status_code == 200

    response = teacher.get(f"/api/activities/{code}/export.csv")
    rendered = response.data.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(rendered, newline="")))
    assert rows[1:] == [
        ["6", "1", "1", "'\tTab", "1"],
        ["7", "1", "1", "'\rCR", "1"],
        ["7", "1", "2", "'\nLF", "1"],
        ["8", "1", "1", "第一格", "1"],
        ["8", "1", "2", "第二格", "1"],
    ]
    assert "'\tTab" in rendered
    assert "'\rCR" in rendered
    assert "'\nLF" in rendered
    assert b"\r\n" in response.data


def test_csv_and_cloud_export_require_teacher_and_ended_phase(app):
    code, _teacher, _group_a, _group_b, adapter = _setup(app)
    student = app.test_client()
    student.post(f"/api/activities/{code}/join", json={"group_number": 1})

    unauthorized_export = _export(student, code)
    unauthorized_csv = student.get(f"/api/activities/{code}/export.csv")
    early_code, early_teacher, _a, _b, _adapter = _setup(app)
    early_csv = early_teacher.get(f"/api/activities/{early_code}/export.csv")

    assert unauthorized_export.status_code == 403
    assert unauthorized_csv.status_code == 403
    assert early_csv.status_code == 409
    assert adapter.write_calls == []


def test_missing_credentials_message_names_expected_file_without_oauth(tmp_path):
    with pytest.raises(SheetsAdapterError, match="client_secret.json"):
        GoogleSheetsAdapter.from_user_credentials(tmp_path)
