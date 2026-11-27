import pytest
from flask import session

from quiz_buzzer import create_app
from quiz_buzzer.data.database import get_db
from quiz_buzzer.services.security import (
    authenticate_teacher,
    create_protected_activity,
    hash_activity_password,
    is_teacher_authenticated,
    verify_activity_password,
)


def test_activity_password_is_hashed_and_can_be_verified(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "auth.sqlite3")})
    with app.app_context():
        database = get_db()
        activity_id, _code = create_protected_activity(database, 4, "correct horse")
        stored = database.execute(
            "SELECT password_hash FROM activities WHERE id = ?", (activity_id,)
        ).fetchone()["password_hash"]

    assert stored != "correct horse"
    assert verify_activity_password(stored, "correct horse")
    assert not verify_activity_password(stored, "wrong password")


@pytest.mark.parametrize("password", ["short", "x" * 65, "        "])
def test_invalid_activity_passwords_are_rejected(password):
    with pytest.raises(ValueError):
        hash_activity_password(password)


def test_activity_code_collision_retries_with_a_unique_code(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "codes.sqlite3")})
    generated = iter(["SAMECODE", "NEXTCODE"])
    with app.app_context():
        database = get_db()
        first_id, first_code = create_protected_activity(
            database, 2, "first password", lambda: next(generated)
        )
        second_id, second_code = create_protected_activity(
            database, 3, "second password", lambda: next(generated)
        )

        assert first_id != second_id
        assert first_code == "SAMECODE"
        assert second_code == "NEXTCODE"


def test_teacher_session_is_granted_only_for_valid_password(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "session.sqlite3")})
    with app.app_context():
        database = get_db()
        activity_id, _code = create_protected_activity(database, 1, "teacher pass")

    with app.test_request_context("/"):
        database = get_db()
        assert authenticate_teacher(database, activity_id, "teacher pass", session)
        assert is_teacher_authenticated(session, activity_id)
        assert not authenticate_teacher(database, activity_id, "wrong pass", session)
        assert not is_teacher_authenticated(session, activity_id)
