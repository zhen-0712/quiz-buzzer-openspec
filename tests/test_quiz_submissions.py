from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from quiz_buzzer import create_app
from quiz_buzzer.data.database import connect, get_db


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-session-signing-key",
            "DATABASE": str(tmp_path / "submissions.sqlite3"),
        }
    )


def _prepare_activity(app, answer_count=1, group_count=3, active=False):
    teacher = app.test_client()
    created = teacher.post(
        "/api/activities", json={"group_count": group_count, "password": "teacher pass"}
    ).get_json()
    code = created["activity_code"]
    students = [app.test_client() for _ in range(group_count)]
    for number, student in enumerate(students, start=1):
        assert student.post(
            f"/api/activities/{code}/join", json={"group_number": number}
        ).status_code == 200
    with app.app_context():
        database = get_db()
        activity = database.execute("SELECT id FROM activities WHERE code = ?", (code,)).fetchone()
        database.execute(
            "INSERT INTO questions (activity_id, position, question_number, answer_count) "
            "VALUES (?, 0, '1', ?)",
            (activity["id"], answer_count),
        )
        if active:
            database.execute("UPDATE activities SET phase = 'active' WHERE id = ?", (activity["id"],))
        database.commit()
    return code, teacher, students


def _submit(student, code, answers, question_number="1"):
    return student.post(
        f"/api/activities/{code}/submissions",
        json={"question_number": question_number, "answers": answers},
    )


@pytest.mark.parametrize(
    ("answers", "error"),
    [
        (["only one"], "answer_count_mismatch"),
        (["first", "second", "extra"], "answer_count_mismatch"),
        (["  \t "], "blank_answer"),
        (["x" * 201], "answer_too_long"),
    ],
)
def test_invalid_whole_question_submission_is_rejected_without_partial_rows(app, answers, error):
    code, _teacher, students = _prepare_activity(app, answer_count=2, active=True)

    response = _submit(students[0], code, answers)

    assert response.status_code == 400
    assert response.get_json()["error"] == error
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 0
        assert get_db().execute("SELECT COUNT(*) FROM submission_answers").fetchone()[0] == 0


@pytest.mark.parametrize("phase", ["preparation", "ended"])
def test_submission_is_rejected_outside_active_phase_without_changing_existing_answer(app, phase):
    code, teacher, students = _prepare_activity(app, active=True)
    first = _submit(students[0], code, ["original"])
    assert first.status_code == 201
    with app.app_context():
        get_db().execute("UPDATE activities SET phase = ? WHERE code = ?", (phase, code))
        get_db().commit()

    rejected = _submit(students[0], code, ["replacement"])

    assert rejected.status_code == 409
    assert rejected.get_json()["error"] == "submission_phase_closed"
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 1
        assert get_db().execute("SELECT answer FROM submission_answers").fetchone()[0] == "original"


def test_resubmission_replaces_effective_answer_and_rejected_resubmission_keeps_sequence(app):
    code, teacher, students = _prepare_activity(app, active=True)
    initial = _submit(students[0], code, ["  alpha  "]).get_json()
    other = _submit(students[1], code, ["beta"]).get_json()
    replacement = _submit(students[0], code, ["gamma"]).get_json()
    rejected = _submit(students[0], code, [" "])

    assert replacement["sequence"] > other["sequence"] > initial["sequence"]
    assert replacement["answers"] == ["gamma"]
    assert rejected.status_code == 400
    view = teacher.get(f"/api/activities/{code}/quiz").get_json()
    current = {item["group_number"]: item for item in view["current_submissions"]}
    assert current[1]["answers"] == ["gamma"]
    assert current[1]["sequence"] == replacement["sequence"]
    assert current[1]["rank"] == 2
    assert current[2]["rank"] == 1
    assert len(view["submissions"]) == 3
    with app.app_context():
        own_history = get_db().execute(
            "SELECT id FROM submissions WHERE group_id = "
            "(SELECT id FROM groups WHERE group_number = 1) ORDER BY id"
        ).fetchall()
        assert [row["id"] for row in own_history] == [initial["sequence"], replacement["sequence"]]


def test_client_clock_does_not_change_server_sequence_or_rank(app):
    code, teacher, students = _prepare_activity(app, active=True)
    first = students[0].post(
        f"/api/activities/{code}/submissions",
        json={"question_number": "1", "answers": ["first"], "client_time": "2099-01-01T00:00:00Z"},
    ).get_json()
    second = students[1].post(
        f"/api/activities/{code}/submissions",
        json={"question_number": "1", "answers": ["second"], "client_time": "1970-01-01T00:00:00Z"},
    ).get_json()

    assert first["sequence"] < second["sequence"]
    current = teacher.get(f"/api/activities/{code}/quiz").get_json()["current_submissions"]
    ranks = {row["group_number"]: row["rank"] for row in current}
    assert ranks == {1: 1, 2: 2}


def test_concurrent_accepted_submissions_get_unique_sequences_and_consistent_ranks(app):
    code, teacher, students = _prepare_activity(app, active=True)
    with app.app_context():
        database_path = app.config["DATABASE"]
        group_ids = [
            row["id"]
            for row in get_db().execute(
                "SELECT id FROM groups WHERE activity_id = "
                "(SELECT id FROM activities WHERE code = ?) ORDER BY group_number",
                (code,),
            ).fetchall()
        ]
    barrier = Barrier(len(group_ids))

    def submit_concurrently(index):
        barrier.wait()
        with app.app_context():
            connection = connect(database_path)
            try:
                from quiz_buzzer.services.submissions import submit_question

                return submit_question(
                    connection, code, group_ids[index], "1", [f"answer-{index}"]
                )
            finally:
                connection.close()

    with ThreadPoolExecutor(max_workers=len(group_ids)) as executor:
        results = list(executor.map(submit_concurrently, range(len(group_ids))))

    sequences = [result["sequence"] for result in results]
    assert len(set(sequences)) == len(group_ids)
    assert sorted(sequences) == list(range(min(sequences), max(sequences) + 1))
    teacher_view = teacher.get(f"/api/activities/{code}/quiz").get_json()
    current = teacher_view["current_submissions"]
    assert sorted(row["sequence"] for row in current) == sorted(sequences)
    by_sequence = sorted(current, key=lambda row: row["sequence"])
    assert [row["rank"] for row in by_sequence] == [1, 2, 3]
    view = students[0].get(f"/api/activities/{code}/quiz").get_json()
    # Students receive only their own row; ranks and acceptance order are teacher-visible.
    assert len(view["submissions"]) == 1
    assert view["submissions"][0]["group_number"] == 1


def test_multi_blank_question_is_one_ranked_submission_and_uses_answer_order(app):
    code, teacher, students = _prepare_activity(app, answer_count=2, active=True)

    accepted = _submit(students[0], code, [" first ", "second"])

    assert accepted.status_code == 201
    assert accepted.get_json()["answers"] == ["first", "second"]
    assert accepted.get_json()["rank"] == 1
    view = teacher.get(f"/api/activities/{code}/quiz").get_json()
    assert len(view["current_submissions"]) == 1
    assert view["current_submissions"][0]["answers"] == ["first", "second"]
    assert view["current_submissions"][0]["rank"] == 1


def test_quiz_api_scopes_student_and_teacher_data_by_phase(app):
    code, teacher, students = _prepare_activity(app, active=False)
    prep_view = students[0].get(f"/api/activities/{code}/quiz").get_json()
    assert prep_view["questions"] == []
    assert "question_number" not in str(prep_view)

    with app.app_context():
        get_db().execute("UPDATE activities SET phase = 'active' WHERE code = ?", (code,))
        get_db().commit()
    active_view = students[0].get(f"/api/activities/{code}/quiz").get_json()
    assert active_view["questions"] == [{"question_number": "1", "answer_count": 1}]
    assert _submit(students[1], code, ["winner answer"]).status_code == 201
    assert _submit(students[0], code, ["own answer"]).status_code == 201
    assert _submit(students[2], code, ["other losing answer"]).status_code == 201

    student_live_view = students[0].get(f"/api/activities/{code}/quiz").get_json()
    assert [row["group_number"] for row in student_live_view["submissions"]] == [1]
    assert "winner answer" not in str(student_live_view)
    assert "other losing answer" not in str(student_live_view)
    teacher_live_view = teacher.get(f"/api/activities/{code}/quiz").get_json()
    assert {row["group_number"] for row in teacher_live_view["current_submissions"]} == {1, 2, 3}
    live_ranks = {
        row["group_number"]: row["rank"]
        for row in teacher_live_view["current_submissions"]
    }
    assert live_ranks == {1: 2, 2: 1, 3: 3}

    with app.app_context():
        get_db().execute("UPDATE activities SET phase = 'ended' WHERE code = ?", (code,))
        get_db().commit()
    student_results = students[1].get(f"/api/activities/{code}/quiz").get_json()
    assert student_results["results"][0]["winner"]["group_number"] == 2
    assert student_results["results"][0]["winner"]["answers"] == ["winner answer"]
    assert student_results["results"][0]["own"]["group_number"] == 2
    assert "own answer" not in str(student_results)
    assert "other losing answer" not in str(student_results)
    teacher_results = teacher.get(f"/api/activities/{code}/quiz").get_json()
    assert len(teacher_results["submissions"]) == 3
    assert len(teacher_results["current_submissions"]) == 3


def test_quiz_api_requires_activity_membership(app):
    code, _teacher, _students = _prepare_activity(app, active=True)

    response = app.test_client().get(f"/api/activities/{code}/quiz")

    assert response.status_code == 403
