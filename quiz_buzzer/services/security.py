"""Password, activity-code, and teacher-session helpers."""

import secrets
import sqlite3
from collections.abc import MutableMapping

from werkzeug.security import check_password_hash, generate_password_hash


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
MAX_CODE_ATTEMPTS = 20


def validate_activity_password(password: str) -> None:
    if not isinstance(password, str) or not 6 <= len(password) <= 64:
        raise ValueError("活動密碼長度必須為 6 至 64 字元")
    if password.isspace():
        raise ValueError("活動密碼不可全為空白")


def hash_activity_password(password: str) -> str:
    validate_activity_password(password)
    return generate_password_hash(password)


def verify_activity_password(password_hash: str, candidate: str) -> bool:
    try:
        return check_password_hash(password_hash, candidate)
    except (TypeError, ValueError):
        return False


def generate_activity_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def create_protected_activity(
    connection: sqlite3.Connection,
    group_count: int,
    password: str,
    code_factory=generate_activity_code,
) -> tuple[int, str]:
    """Create an activity row, retrying generated codes on uniqueness conflicts."""
    if not isinstance(group_count, int) or not 1 <= group_count <= 100:
        raise ValueError("組數必須介於 1 至 100")
    password_hash = hash_activity_password(password)

    for _attempt in range(MAX_CODE_ATTEMPTS):
        code = code_factory()
        try:
            cursor = connection.execute(
                "INSERT INTO activities (code, password_hash, group_count) VALUES (?, ?, ?)",
                (code, password_hash, group_count),
            )
            connection.commit()
            return int(cursor.lastrowid), code
        except sqlite3.IntegrityError as error:
            if "activities.code" not in str(error):
                connection.rollback()
                raise
            connection.rollback()
    raise RuntimeError("無法產生唯一活動代碼，請重試")


def authenticate_teacher(
    connection: sqlite3.Connection,
    activity_id: int,
    password: str,
    session_data: MutableMapping,
) -> bool:
    row = connection.execute(
        "SELECT password_hash FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if row is None or not verify_activity_password(row["password_hash"], password):
        session_data.pop("teacher_activity_id", None)
        return False
    session_data["teacher_activity_id"] = activity_id
    return True


def is_teacher_authenticated(session_data: MutableMapping, activity_id: int) -> bool:
    return session_data.get("teacher_activity_id") == activity_id
