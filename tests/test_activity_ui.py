from pathlib import Path

import pytest

from quiz_buzzer import create_app
from quiz_buzzer.data.database import get_db
from tests.fakes import MemorySheetsAdapter
from tests.workbook_fixtures import load_xlsx_as_sheet_structure


ROOT = Path(__file__).resolve().parents[1]
SHEET_URL = "https://docs.google.com/spreadsheets/d/fake-guided-notes/edit"


@pytest.fixture
def app(tmp_path):
    structure = load_xlsx_as_sheet_structure(
        ROOT / "tests" / "fixtures" / "軟工期末專案_題組_範例.xlsx"
    )
    adapter = MemorySheetsAdapter({SHEET_URL: structure})
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "activity-ui-test-session-key",
            "DATABASE": str(tmp_path / "activity-ui.sqlite3"),
            "SHEETS_ADAPTER": adapter,
        }
    )


def _create_activity(client, group_count=3):
    response = client.post(
        "/api/activities",
        json={"group_count": group_count, "password": "teacher pass"},
    )
    assert response.status_code == 201
    return response.get_json()["activity_code"]


def _join(client, code, group_number):
    response = client.post(
        f"/api/activities/{code}/join", json={"group_number": group_number}
    )
    assert response.status_code == 200
    return response.get_json()


def _advance(client, code, phase):
    response = client.post(
        f"/api/activities/{code}/phase", json={"phase": phase}
    )
    assert response.status_code == 200
    return response.get_json()


def test_home_and_activity_pages_render_teacher_and_student_controls(app):
    teacher = app.test_client()
    home = teacher.get("/").get_data(as_text=True)
    code = _create_activity(teacher)
    activity_page = teacher.get(f"/activities/{code}/status")
    page = activity_page.get_data(as_text=True)

    assert "老師｜建立活動" in home
    assert "老師｜重新登入" in home
    assert "學生｜加入或重新進入" in home
    assert 'min="1" max="100"' in home
    assert 'minlength="6" maxlength="64"' in home
    assert activity_page.headers["Cache-Control"] == "no-store"
    assert 'data-teacher-view hidden' in page
    assert 'data-student-view hidden' in page
    assert "data-import-form" in page
    assert "data-phase-action" in page
    assert "data-student-questions" in page
    assert "data-results-list" in page
    javascript = (ROOT / "quiz_buzzer" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "window.confirm(prompt)" in javascript
    assert 'phaseAction.disabled = phase === "preparation"' in javascript
    assert "window.setInterval(poll, 1000)" in javascript
    assert "localStorage" not in javascript
    assert "sessionStorage" not in javascript


def test_teacher_can_login_from_a_new_session_and_refresh_page(app):
    creating_browser = app.test_client()
    code = _create_activity(creating_browser, group_count=2)
    new_browser = app.test_client()

    wrong = new_browser.post(
        f"/api/activities/{code}/teacher-login", json={"password": "wrong pass"}
    )
    login = new_browser.post(
        f"/api/activities/{code}/teacher-login", json={"password": "teacher pass"}
    )
    first_status = new_browser.get(f"/api/activities/{code}/status").get_json()
    first_page = new_browser.get(f"/activities/{code}/status")
    refreshed_page = new_browser.get(f"/activities/{code}/status")
    refreshed_status = new_browser.get(f"/api/activities/{code}/status").get_json()

    assert wrong.status_code == 401
    assert login.status_code == 200
    assert first_status["role"] == "teacher"
    assert first_page.status_code == refreshed_page.status_code == 200
    assert refreshed_status["role"] == "teacher"


def test_student_join_page_exposes_configured_group_range(app):
    teacher = app.test_client()
    code = _create_activity(teacher, group_count=2)
    student = app.test_client()
    status = student.get(f"/api/activities/{code}/status").get_json()
    joined = _join(student, code, 2)
    page = student.get(f"/activities/{code}/status")

    assert status["group_count"] == 2
    assert joined["group_number"] == 2
    assert page.status_code == 200
    assert page.headers["Cache-Control"] == "no-store"


def test_fake_sheets_end_to_end_flow_and_utf8_answers_are_preserved(app):
    teacher = app.test_client()
    code = _create_activity(teacher, group_count=2)
    page = teacher.get(f"/activities/{code}/status")
    student_a = app.test_client()
    student_b = app.test_client()
    assert _join(student_a, code, 1)["phase"] == "preparation"
    assert _join(student_b, code, 2)["phase"] == "preparation"

    imported = teacher.post(
        f"/api/activities/{code}/import", json={"sheet_url": SHEET_URL}
    )
    assert imported.status_code == 200
    assert imported.get_json()["question_count"] == 4
    assert imported.get_json()["questions"] == [
        {"question_number": "1", "answer_count": 2},
        {"question_number": "2", "answer_count": 2},
        {"question_number": "3", "answer_count": 1},
        {"question_number": "4", "answer_count": 1},
    ]
    teacher_preparation = teacher.get(f"/api/activities/{code}/quiz").get_json()
    assert len(teacher_preparation["questions"]) == 4

    _advance(teacher, code, "active")
    student_questions = student_a.get(f"/api/activities/{code}/quiz").get_json()
    assert len(student_questions["questions"]) == 4
    assert student_questions["questions"][0] == {"question_number": "1", "answer_count": 2}

    answer_a_first = ["中文初答一", "地球繞著太陽公轉"]
    answer_b = ["勝出答案一", "勝出答案二"]
    answer_a_retry = ["中文重送一", "月球繞著地球運行"]
    for client, answers in (
        (student_a, answer_a_first),
        (student_b, answer_b),
        (student_a, answer_a_retry),
    ):
        response = client.post(
            f"/api/activities/{code}/submissions",
            json={"question_number": "1", "answers": answers},
        )
        assert response.status_code == 201
        assert response.get_json()["status"] == "已送出"

    student_live = student_a.get(f"/api/activities/{code}/quiz").get_json()
    assert student_live["submissions"] == [
        {"question_number": "1", "answers": answer_a_retry, "status": "已送出"}
    ]
    assert not {"rank", "sequence", "accepted_at", "is_effective"} & _all_keys(student_live)
    live_teacher = teacher.get(f"/api/activities/{code}/quiz").get_json()
    live_ranks = {
        row["group_number"]: row["rank"]
        for row in live_teacher["current_submissions"]
    }
    assert live_ranks == {2: 1, 1: 2}

    with app.app_context():
        persisted = get_db().execute(
            "SELECT a.answer FROM submission_answers a "
            "JOIN submissions s ON s.id = a.submission_id "
            "JOIN groups g ON g.id = s.group_id "
            "JOIN questions q ON q.id = s.question_id "
            "WHERE g.group_number = 1 AND q.question_number = '1' "
            "AND s.id = (SELECT MAX(s2.id) FROM submissions s2 "
            "WHERE s2.group_id = g.id AND s2.question_id = q.id) "
            "ORDER BY a.position"
        ).fetchall()
    assert [row["answer"] for row in persisted] == answer_a_retry
    _advance(teacher, code, "ended")
    result_a = student_a.get(f"/api/activities/{code}/quiz").get_json()
    result_b = student_b.get(f"/api/activities/{code}/quiz").get_json()
    assert result_a["results"][0]["winner"]["group_number"] == 2
    assert result_a["results"][0]["winner"]["answers"] == answer_b
    assert result_a["results"][0]["own"]["answers"] == answer_a_retry
    assert result_a["results"][0]["own"]["rank"] == 2
    assert result_b["results"][0]["own"]["rank"] == 1
    assert "中文重送一" not in str(result_b)
    assert "中文初答一" not in str(result_a)
    teacher_ended = teacher.get(f"/api/activities/{code}/quiz").get_json()
    assert len(teacher_ended["submissions"]) == 3
    assert len(teacher_ended["current_submissions"]) == 2
    assert page.status_code == 200


def _all_keys(value):
    if isinstance(value, dict):
        found = set(value)
        for child in value.values():
            found.update(_all_keys(child))
        return found
    if isinstance(value, list):
        found = set()
        for child in value:
            found.update(_all_keys(child))
        return found
    return set()
