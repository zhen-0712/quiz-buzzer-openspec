import json
import subprocess
import sys
import pytest
import time
from pathlib import Path

from quiz_buzzer import create_app
from quiz_buzzer.data.database import get_db
from quiz_buzzer.services.activities import create_activity


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-session-signing-key",
            "DATABASE": str(tmp_path / "activities.sqlite3"),
        }
    )


@pytest.mark.parametrize(
    ("group_count", "password"),
    [(1, "123456"), (100, "p" * 64)],
)
def test_create_activity_accepts_boundary_values_and_hashes_password(
    app, group_count, password
):
    client = app.test_client()

    response = client.post(
        "/api/activities", json={"group_count": group_count, "password": password}
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["activity_code"]
    assert payload["phase"] == "preparation"
    with app.app_context():
        row = get_db().execute(
            "SELECT group_count, password_hash FROM activities WHERE code = ?",
            (payload["activity_code"],),
        ).fetchone()
        assert row["group_count"] == group_count
        assert row["password_hash"] != password


@pytest.mark.parametrize(
    ("group_count", "password"),
    [
        (0, "123456"),
        (101, "123456"),
        (True, "123456"),
        (1, "12345"),
        (1, "p" * 65),
        (1, "      "),
    ],
)
def test_create_activity_rejects_invalid_group_count_or_password(
    app, group_count, password
):
    response = app.test_client().post(
        "/api/activities", json={"group_count": group_count, "password": password}
    )

    assert response.status_code == 400
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 0


def test_teacher_login_uses_the_activity_password(app):
    client = app.test_client()
    created = client.post(
        "/api/activities", json={"group_count": 3, "password": "teacher pass"}
    ).get_json()

    client.post("/api/activities/unused/teacher-login", json={"password": "x"})
    wrong = client.post(
        f"/api/activities/{created['activity_code']}/teacher-login",
        json={"password": "wrong password"},
    )
    right = client.post(
        f"/api/activities/{created['activity_code']}/teacher-login",
        json={"password": "teacher pass"},
    )

    assert wrong.status_code == 401
    assert right.status_code == 200
    assert right.get_json()["role"] == "teacher"


def _create_activity(client, group_count=3):
    response = client.post(
        "/api/activities", json={"group_count": group_count, "password": "teacher pass"}
    )
    assert response.status_code == 201
    return response.get_json()["activity_code"]


@pytest.mark.parametrize("phase", ["preparation", "active"])
def test_students_can_join_during_preparation_and_active_phase(app, phase):
    teacher = app.test_client()
    code = _create_activity(teacher)
    if phase == "active":
        with app.app_context():
            get_db().execute("UPDATE activities SET phase = 'active' WHERE code = ?", (code,))
            get_db().commit()

    student = app.test_client()
    response = student.post(f"/api/activities/{code}/join", json={"group_number": 2})

    assert response.status_code == 200
    assert response.get_json() == {
        "role": "student",
        "group_number": 2,
        "phase": phase,
        "view": "activity",
        "read_only": False,
    }


def test_reentering_a_group_reuses_identity_and_preserves_existing_answers(app):
    teacher = app.test_client()
    code = _create_activity(teacher)
    with app.app_context():
        database = get_db()
        activity_id = database.execute(
            "SELECT id FROM activities WHERE code = ?", (code,)
        ).fetchone()["id"]
        group_id = database.execute(
            "INSERT INTO groups (activity_id, group_number) VALUES (?, ?)",
            (activity_id, 1),
        ).lastrowid
        question_id = database.execute(
            "INSERT INTO questions (activity_id, position, question_number, answer_count) "
            "VALUES (?, 0, '1', 1)",
            (activity_id,),
        ).lastrowid
        submission_id = database.execute(
            "INSERT INTO submissions (question_id, group_id) VALUES (?, ?)",
            (question_id, group_id),
        ).lastrowid
        database.execute(
            "INSERT INTO submission_answers (submission_id, position, answer) VALUES (?, 0, ?)",
            (submission_id, "保留答案"),
        )
        database.commit()

    first = app.test_client().post(
        f"/api/activities/{code}/join", json={"group_number": 1}
    )
    second = app.test_client().post(
        f"/api/activities/{code}/join", json={"group_number": 1}
    )

    assert first.status_code == second.status_code == 200
    with app.app_context():
        database = get_db()
        assert database.execute(
            "SELECT COUNT(*) FROM groups WHERE activity_id = ? AND group_number = 1",
            (activity_id,),
        ).fetchone()[0] == 1
        assert database.execute(
            "SELECT answer FROM submission_answers WHERE submission_id = ?",
            (submission_id,),
        ).fetchone()["answer"] == "保留答案"


@pytest.mark.parametrize(
    ("activity_code", "group_number", "expected_status", "expected_error"),
    [
        ("missing", 1, 404, "activity_not_found"),
        (None, 4, 400, "invalid_group_number"),
        (None, 0, 400, "invalid_group_number"),
        (None, True, 400, "invalid_group_number"),
    ],
)
def test_join_rejects_unknown_activity_or_out_of_range_group(
    app, activity_code, group_number, expected_status, expected_error
):
    code = activity_code or _create_activity(app.test_client(), group_count=3)

    response = app.test_client().post(
        f"/api/activities/{code}/join", json={"group_number": group_number}
    )

    assert response.status_code == expected_status
    assert response.get_json()["error"] == expected_error


def test_student_entering_ended_activity_gets_read_only_result_mode(app):
    teacher = app.test_client()
    code = _create_activity(teacher, group_count=2)
    with app.app_context():
        database = get_db()
        database.execute("UPDATE activities SET phase = 'ended' WHERE code = ?", (code,))
        database.commit()

    response = app.test_client().post(
        f"/api/activities/{code}/join", json={"group_number": 2}
    )

    assert response.status_code == 200
    assert response.get_json()["view"] == "results"
    assert response.get_json()["read_only"] is True
    assert response.get_json()["phase"] == "ended"


def _add_question(app, code):
    with app.app_context():
        database = get_db()
        activity_id = database.execute(
            "SELECT id FROM activities WHERE code = ?", (code,)
        ).fetchone()["id"]
        database.execute(
            "INSERT INTO questions (activity_id, position, question_number, answer_count) "
            "VALUES (?, 0, '1', 1)",
            (activity_id,),
        )
        database.commit()


def test_teacher_cannot_start_until_at_least_one_question_is_imported(app):
    client = app.test_client()
    code = _create_activity(client)

    response = client.post(
        f"/api/activities/{code}/phase", json={"phase": "active"}
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "questions_required"
    with app.app_context():
        activity = get_db().execute(
            "SELECT phase, phase_version FROM activities WHERE code = ?", (code,)
        ).fetchone()
        assert activity["phase"] == "preparation"
        assert activity["phase_version"] == 0


def test_teacher_advances_through_phases_in_order_after_question_import(app):
    client = app.test_client()
    code = _create_activity(client)
    _add_question(app, code)

    first = client.post(f"/api/activities/{code}/phase", json={"phase": "active"})
    second = client.post(f"/api/activities/{code}/phase", json={"phase": "ended"})

    assert first.status_code == second.status_code == 200
    assert first.get_json() == {"phase": "active", "phase_version": 1}
    assert second.get_json() == {"phase": "ended", "phase_version": 2}


@pytest.mark.parametrize(
    ("first_target", "second_target"),
    [("ended", None), ("active", "preparation"), ("active", "active")],
)
def test_teacher_cannot_skip_reverse_or_repeat_a_phase(app, first_target, second_target):
    client = app.test_client()
    code = _create_activity(client)
    if first_target == "active":
        _add_question(app, code)

    response = client.post(
        f"/api/activities/{code}/phase", json={"phase": first_target}
    )
    if second_target is None:
        assert response.status_code == 409
        assert response.get_json()["error"] == "invalid_phase_transition"
    else:
        assert response.status_code == 200
        response = client.post(
            f"/api/activities/{code}/phase", json={"phase": second_target}
        )
        assert response.status_code == 409
        assert response.get_json()["error"] == "invalid_phase_transition"


def test_unauthenticated_or_wrong_activity_teacher_cannot_change_phase(app):
    creator = app.test_client()
    first_code = _create_activity(creator)
    other_code = _create_activity(creator)
    _add_question(app, first_code)
    _add_question(app, other_code)

    anonymous = app.test_client()
    assert anonymous.post(
        f"/api/activities/{first_code}/phase", json={"phase": "active"}
    ).status_code == 403

    teacher = app.test_client()
    assert teacher.post(
        f"/api/activities/{first_code}/teacher-login", json={"password": "teacher pass"}
    ).status_code == 200
    assert teacher.post(
        f"/api/activities/{other_code}/phase", json={"phase": "active"}
    ).status_code == 403


def test_status_endpoint_returns_only_role_scoped_group_information(app):
    teacher = app.test_client()
    code = _create_activity(teacher, group_count=3)
    first_student = app.test_client()
    second_student = app.test_client()
    first_student.post(f"/api/activities/{code}/join", json={"group_number": 1})
    second_student.post(f"/api/activities/{code}/join", json={"group_number": 2})

    first_status = first_student.get(f"/api/activities/{code}/status")
    teacher_status = teacher.get(f"/api/activities/{code}/status")
    guest_status = app.test_client().get(f"/api/activities/{code}/status")

    assert first_status.status_code == 200
    assert first_status.headers["Cache-Control"] == "no-store"
    assert first_status.get_json() == {
        "phase": "preparation",
        "phase_version": 0,
        "role": "student",
        "group_number": 1,
    }
    assert teacher_status.get_json()["role"] == "teacher"
    assert teacher_status.get_json()["joined_groups"] == [1, 2]
    assert guest_status.get_json() == {
        "phase": "preparation",
        "phase_version": 0,
        "role": "guest",
    }


def test_status_endpoint_reflects_phase_change_within_two_seconds(app):
    teacher = app.test_client()
    code = _create_activity(teacher)
    _add_question(app, code)
    student = app.test_client()
    student.post(f"/api/activities/{code}/join", json={"group_number": 1})

    started = time.monotonic()
    transition = teacher.post(
        f"/api/activities/{code}/phase", json={"phase": "active"}
    )
    status = student.get(f"/api/activities/{code}/status")
    elapsed = time.monotonic() - started

    assert transition.status_code == 200
    assert status.get_json()["phase"] == "active"
    assert status.get_json()["phase_version"] == 1
    assert elapsed < 2


def test_reconnected_student_reenters_and_reads_current_server_phase(app):
    teacher = app.test_client()
    code = _create_activity(teacher)
    _add_question(app, code)
    assert teacher.post(
        f"/api/activities/{code}/phase", json={"phase": "active"}
    ).status_code == 200

    reconnected_student = app.test_client()
    joined = reconnected_student.post(
        f"/api/activities/{code}/join", json={"group_number": 3}
    )
    status = reconnected_student.get(f"/api/activities/{code}/status")

    assert joined.status_code == 200
    assert status.get_json()["phase"] == "active"
    assert status.get_json()["group_number"] == 3


def test_status_page_and_javascript_poll_once_per_second(app):
    teacher = app.test_client()
    code = _create_activity(teacher)

    page = teacher.get(f"/activities/{code}/status")
    javascript = (Path(__file__).resolve().parents[1] / "quiz_buzzer/static/js/app.js").read_text(
        encoding="utf-8"
    )

    assert page.status_code == 200
    assert 'data-activity-code="' in page.get_data(as_text=True)
    assert "目前階段：<strong data-phase-label>準備</strong>" in page.get_data(as_text=True)
    assert "fetch(" in javascript
    assert "window.setInterval(refreshActivityStatus, 1000)" in javascript
    assert "data-connection-status" in javascript


def test_activity_and_submission_sequence_survive_a_new_process(tmp_path):
    database_path = tmp_path / "restart.sqlite3"
    config = {
        "TESTING": True,
        "SECRET_KEY": "stable-test-session-key",
        "DATABASE": str(database_path),
    }
    first_app = create_app(config)
    with first_app.app_context():
        database = get_db()
        activity_id, code = create_activity(database, 4, "teacher pass")
        question_id = database.execute(
            "INSERT INTO questions (activity_id, position, question_number, answer_count) "
            "VALUES (?, 0, 'Q1', 1)",
            (activity_id,),
        ).lastrowid
        group_id = database.execute(
            "INSERT INTO groups (activity_id, group_number) VALUES (?, 2)",
            (activity_id,),
        ).lastrowid
        first_submission_id = database.execute(
            "INSERT INTO submissions (question_id, group_id) VALUES (?, ?)",
            (question_id, group_id),
        ).lastrowid
        database.execute(
            "INSERT INTO submission_answers (submission_id, position, answer) "
            "VALUES (?, 0, 'saved answer')",
            (first_submission_id,),
        )
        database.execute(
            "UPDATE activities SET phase = 'active', phase_version = 1 WHERE id = ?",
            (activity_id,),
        )
        database.commit()

    restarted_process_script = """
import json
import sys
from quiz_buzzer import create_app
from quiz_buzzer.data.database import get_db

app = create_app({"TESTING": True, "SECRET_KEY": "stable-test-session-key", "DATABASE": sys.argv[1]})
with app.app_context():
    db = get_db()
    activity = db.execute("SELECT id, phase, phase_version FROM activities WHERE code = ?", (sys.argv[2],)).fetchone()
    question = db.execute("SELECT id, question_number FROM questions WHERE activity_id = ?", (activity["id"],)).fetchone()
    group = db.execute("SELECT id, group_number FROM groups WHERE activity_id = ?", (activity["id"],)).fetchone()
    saved = db.execute("SELECT answer FROM submission_answers WHERE submission_id = ?", (int(sys.argv[3]),)).fetchone()
    next_id = db.execute("INSERT INTO submissions (question_id, group_id) VALUES (?, ?)", (question["id"], group["id"])).lastrowid
    db.execute("INSERT INTO submission_answers (submission_id, position, answer) VALUES (?, 0, 'new answer')", (next_id,))
    db.commit()
    print(json.dumps({"phase": activity["phase"], "version": activity["phase_version"], "question": question["question_number"], "group": group["group_number"], "saved": saved["answer"], "first_sequence": int(sys.argv[3]), "next_sequence": next_id}))
"""
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            restarted_process_script,
            str(database_path),
            code,
            str(first_submission_id),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    restored = json.loads(process.stdout)

    assert restored == {
        "phase": "active",
        "version": 1,
        "question": "Q1",
        "group": 2,
        "saved": "saved answer",
        "first_sequence": first_submission_id,
        "next_sequence": first_submission_id + 1,
    }

    restarted_app = create_app(config)
    student = restarted_app.test_client()
    reentered = student.post(f"/api/activities/{code}/join", json={"group_number": 2})
    status = student.get(f"/api/activities/{code}/status")
    assert reentered.status_code == 200
    assert status.get_json()["phase"] == "active"
    assert status.get_json()["group_number"] == 2
