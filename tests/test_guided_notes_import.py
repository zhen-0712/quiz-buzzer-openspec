import json

import pytest

from quiz_buzzer import create_app
from quiz_buzzer.data.database import get_db
from quiz_buzzer.sheets.models import MergedRange, SpreadsheetStructure, WorksheetGrid
from tests.fakes import MemorySheetsAdapter


def make_structure(spreadsheet_id, title, values, merged_ranges=None):
    return SpreadsheetStructure(
        spreadsheet_id=spreadsheet_id,
        worksheets=[
            WorksheetGrid(
                worksheet_id="41",
                title=title,
                values=values,
                merged_ranges=list(merged_ranges or []),
            )
        ],
    )


@pytest.fixture
def import_context(tmp_path):
    adapter = MemorySheetsAdapter()
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-session-key",
            "DATABASE": str(tmp_path / "guided-import.sqlite3"),
            "SHEETS_ADAPTER": adapter,
        }
    )
    client = app.test_client()
    created = client.post(
        "/api/activities", json={"group_count": 3, "password": "teacher pass"}
    )
    assert created.status_code == 201
    return app, client, adapter, created.get_json()["activity_code"]


def test_import_uses_sheet_question_count_and_reimport_replaces_old_questions(import_context):
    app, client, adapter, code = import_context
    adapter.register(
        "fake://first",
        make_structure(
            "sheet-first",
            "Guided",
            [["題號", "作答"], ["1", None], ["2", None]],
        ),
    )

    first = client.post(
        f"/api/activities/{code}/import", json={"sheet_url": "fake://first"}
    )
    assert first.status_code == 200
    assert first.get_json()["question_count"] == 2
    assert [q["question_number"] for q in first.get_json()["questions"]] == ["1", "2"]

    adapter.register(
        "fake://replacement",
        make_structure(
            "sheet-replacement",
            "New Notes",
            [["題號", "作答"], ["9", None], [None, None]],
            [MergedRange(1, 3, 0, 1)],
        ),
    )
    second = client.post(
        f"/api/activities/{code}/import",
        json={"sheet_url": "fake://replacement"},
    )

    assert second.status_code == 200
    assert second.get_json()["question_count"] == 1
    assert second.get_json()["questions"] == [
        {"question_number": "9", "answer_count": 2}
    ]
    with app.app_context():
        database = get_db()
        questions = database.execute(
            "SELECT question_number, answer_count FROM questions ORDER BY position"
        ).fetchall()
        activity = database.execute(
            "SELECT source_url, source_spreadsheet_id, source_structure_json FROM activities "
            "WHERE code = ?",
            (code,),
        ).fetchone()
        cells = database.execute(
            "SELECT position, row_index, column_index, a1_address FROM answer_cells "
            "ORDER BY position"
        ).fetchall()

    assert [(row["question_number"], row["answer_count"]) for row in questions] == [("9", 2)]
    assert activity["source_url"] == "fake://replacement"
    assert activity["source_spreadsheet_id"] == "sheet-replacement"
    snapshot = json.loads(activity["source_structure_json"])
    assert [q["question_number"] for q in snapshot["questions"]] == ["9"]
    assert [blank["a1_address"] for blank in snapshot["questions"][0]["blanks"]] == [
        "B2",
        "B3",
    ]
    assert [(cell["position"], cell["a1_address"]) for cell in cells] == [
        (0, "B2"),
        (1, "B3"),
    ]


def test_failed_reimport_reports_worksheet_and_position_and_preserves_previous_questions(
    import_context,
):
    app, client, adapter, code = import_context
    adapter.register(
        "fake://initial",
        make_structure("first", "Initial", [["題號", "作答"], ["Q1", None]]),
    )
    assert client.post(
        f"/api/activities/{code}/import", json={"sheet_url": "fake://initial"}
    ).status_code == 200
    adapter.register(
        "fake://ambiguous",
        make_structure(
            "bad",
            "Ambiguous Notes",
            [["題號", "敘述", "作答"], ["Q2", "valid row", None], [None, "orphan", None]],
        ),
    )

    response = client.post(
        f"/api/activities/{code}/import", json={"sheet_url": "fake://ambiguous"}
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "sheet_structure_invalid"
    assert "工作表「Ambiguous Notes」A3" in response.get_json()["message"]
    with app.app_context():
        database = get_db()
        questions = database.execute(
            "SELECT question_number FROM questions ORDER BY position"
        ).fetchall()
        activity = database.execute(
            "SELECT source_url, source_spreadsheet_id, source_structure_json FROM activities "
            "WHERE code = ?",
            (code,),
        ).fetchone()
    assert [row["question_number"] for row in questions] == ["Q1"]
    assert activity["source_url"] == "fake://initial"
    assert activity["source_spreadsheet_id"] == "first"
    assert json.loads(activity["source_structure_json"])["worksheet_id"] == "41"


def test_import_uses_first_matching_worksheet_and_ignores_later_candidates(import_context):
    _app, client, adapter, code = import_context
    adapter.register(
        "fake://multi-sheet",
        SpreadsheetStructure(
            "multi-sheet",
            [
                WorksheetGrid("1", "說明", [["請先閱讀說明"]]),
                WorksheetGrid("2", "學習單", [["題號", "作答"], ["1", None]]),
                WorksheetGrid("3", "其他題目", [["題號", "作答"], ["9", None]]),
            ],
        ),
    )

    response = client.post(
        f"/api/activities/{code}/import", json={"sheet_url": "fake://multi-sheet"}
    )

    assert response.status_code == 200
    assert response.get_json()["worksheet_id"] == "2"
    assert [row["question_number"] for row in response.get_json()["questions"]] == ["1"]


def test_import_does_not_fall_back_after_first_candidate_fails(import_context):
    _app, client, adapter, code = import_context
    adapter.register(
        "fake://multi-sheet-invalid",
        SpreadsheetStructure(
            "multi-sheet-invalid",
            [
                WorksheetGrid(
                    "2",
                    "第一份學習單",
                    [["題號", "作答"], ["1", None], [None, "無法歸屬"]],
                ),
                WorksheetGrid("3", "第二份學習單", [["題號", "作答"], ["9", None]]),
            ],
        ),
    )

    response = client.post(
        f"/api/activities/{code}/import",
        json={"sheet_url": "fake://multi-sheet-invalid"},
    )

    assert response.status_code == 400
    assert "第一份學習單" in response.get_json()["message"]
    assert "A3" in response.get_json()["message"]


def test_import_with_gid_reads_only_the_requested_worksheet(import_context):
    _app, client, adapter, code = import_context
    adapter.register(
        "fake://gid-sheet?gid=3",
        SpreadsheetStructure(
            "gid-sheet",
            [
                WorksheetGrid("2", "沒有標題", [["封面"]]),
                WorksheetGrid("3", "指定學習單", [["題號", "作答"], ["3", None]]),
                WorksheetGrid("4", "其他學習單", [["題號", "作答"], ["4", None]]),
            ],
        ),
    )

    response = client.post(
        f"/api/activities/{code}/import", json={"sheet_url": "fake://gid-sheet?gid=3"}
    )

    assert response.status_code == 200
    assert response.get_json()["worksheet_id"] == "3"
    assert [row["question_number"] for row in response.get_json()["questions"]] == ["3"]


def test_import_rejects_gid_that_does_not_exist_with_clear_error(import_context):
    _app, client, adapter, code = import_context
    adapter.register(
        "fake://missing-gid?gid=999",
        SpreadsheetStructure(
            "missing-gid",
            [WorksheetGrid("3", "學習單", [["題號", "作答"], ["3", None]])],
        ),
    )

    response = client.post(
        f"/api/activities/{code}/import",
        json={"sheet_url": "fake://missing-gid?gid=999"},
    )

    assert response.status_code == 502
    assert "fake worksheet not found: 999" in response.get_json()["message"]


def test_import_with_gid_without_headers_does_not_scan_other_worksheets(import_context):
    _app, client, adapter, code = import_context
    adapter.register(
        "fake://gid-no-headers?gid=2",
        SpreadsheetStructure(
            "gid-no-headers",
            [
                WorksheetGrid("2", "指定說明頁", [["這一頁沒有題號或作答標題"]]),
                WorksheetGrid("3", "其他學習單", [["題號", "作答"], ["3", None]]),
            ],
        ),
    )

    response = client.post(
        f"/api/activities/{code}/import",
        json={"sheet_url": "fake://gid-no-headers?gid=2"},
    )

    assert response.status_code == 400
    assert "找不到「題號」與「作答」標題" in response.get_json()["message"]


def test_import_is_rejected_outside_preparation_without_reading_sheet(import_context):
    _app, teacher, adapter, code = import_context
    adapter.register(
        "fake://one-question",
        make_structure("sheet", "Guided", [["題號", "作答"], ["1", None]]),
    )
    assert teacher.post(
        f"/api/activities/{code}/import", json={"sheet_url": "fake://one-question"}
    ).status_code == 200
    assert teacher.post(
        f"/api/activities/{code}/phase", json={"phase": "active"}
    ).status_code == 200

    active_response = teacher.post(
        f"/api/activities/{code}/import", json={"sheet_url": "fake://one-question"}
    )
    assert active_response.status_code == 409
    assert active_response.get_json()["error"] == "import_phase_closed"
    assert teacher.post(
        f"/api/activities/{code}/phase", json={"phase": "ended"}
    ).status_code == 200
    ended_response = teacher.post(
        f"/api/activities/{code}/import", json={"sheet_url": "fake://one-question"}
    )
    assert ended_response.status_code == 409
    assert ended_response.get_json()["error"] == "import_phase_closed"
    assert adapter.read_calls == ["fake://one-question"]


def test_only_authenticated_teacher_can_import_and_read_failure_is_reported(import_context):
    _app, teacher, adapter, code = import_context
    anonymous = _app.test_client()

    denied = anonymous.post(
        f"/api/activities/{code}/import", json={"sheet_url": "fake://missing"}
    )
    assert denied.status_code == 403
    assert adapter.read_calls == []

    failed = teacher.post(
        f"/api/activities/{code}/import", json={"sheet_url": "fake://missing"}
    )
    assert failed.status_code == 502
    assert failed.get_json()["error"] == "sheet_read_failed"
    assert "fake sheet is not registered" in failed.get_json()["message"]
