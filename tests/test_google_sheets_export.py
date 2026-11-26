import copy
import csv
import io
from pathlib import Path

import pytest

from quiz_buzzer import create_app
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
        ("question_number", "題號或題目順序"),
        ("blank_count", "填空數"),
        ("question_order", "題號或題目順序"),
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


def test_csv_is_winner_only_utf8_bom_and_quotes_each_answer_row(app):
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
        ["題號", "組別", "答案", "搶答順位"],
        ["1", "1", answers[0], "1"],
        ["1", "1", answers[1], "1"],
    ]


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
