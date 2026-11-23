"""Activity lifecycle operations backed by the local database."""

import sqlite3
from collections.abc import MutableMapping
import json

from quiz_buzzer.services.security import authenticate_teacher, create_protected_activity
from quiz_buzzer.sheets.models import SheetsAdapterError
from quiz_buzzer.sheets.parser import SheetParseError, parse_guided_notes


PHASES = ("preparation", "active", "ended")


class ActivityError(Exception):
    def __init__(self, message: str, status_code: int = 400, error_code: str = "invalid_request"):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


def find_activity(connection: sqlite3.Connection, activity_code: str):
    if not isinstance(activity_code, str):
        return None
    return connection.execute(
        "SELECT * FROM activities WHERE code = ?", (activity_code.strip(),)
    ).fetchone()


def create_activity(
    connection: sqlite3.Connection,
    group_count: object,
    password: object,
    code_factory=None,
) -> tuple[int, str]:
    if type(group_count) is not int or not 1 <= group_count <= 100:
        raise ActivityError("組數必須介於 1 至 100", error_code="invalid_group_count")
    if not isinstance(password, str):
        raise ActivityError("請輸入活動密碼", error_code="invalid_password")
    try:
        if code_factory is None:
            return create_protected_activity(connection, group_count, password)
        return create_protected_activity(connection, group_count, password, code_factory)
    except ValueError as error:
        raise ActivityError(str(error), error_code="invalid_password") from error


def login_teacher(
    connection: sqlite3.Connection,
    activity_code: str,
    password: object,
    session_data: MutableMapping,
) -> int:
    activity = find_activity(connection, activity_code)
    if activity is None:
        raise ActivityError("找不到此活動代碼", 404, "activity_not_found")
    if not isinstance(password, str):
        password = ""
    if not authenticate_teacher(connection, activity["id"], password, session_data):
        raise ActivityError("活動密碼錯誤", 401, "invalid_password")
    session_data.pop("student_activity_id", None)
    session_data.pop("student_group_id", None)
    return int(activity["id"])


def join_activity(
    connection: sqlite3.Connection,
    activity_code: str,
    group_number: object,
    session_data: MutableMapping,
) -> dict:
    activity = find_activity(connection, activity_code)
    if activity is None:
        raise ActivityError("找不到此活動代碼", 404, "activity_not_found")
    if type(group_number) is not int or not 1 <= group_number <= activity["group_count"]:
        raise ActivityError(
            f"組別編號必須介於 1 至 {activity['group_count']}",
            400,
            "invalid_group_number",
        )

    connection.execute(
        "INSERT OR IGNORE INTO groups (activity_id, group_number) VALUES (?, ?)",
        (activity["id"], group_number),
    )
    connection.commit()
    group = connection.execute(
        "SELECT id FROM groups WHERE activity_id = ? AND group_number = ?",
        (activity["id"], group_number),
    ).fetchone()

    session_data.clear()
    session_data["student_activity_id"] = int(activity["id"])
    session_data["student_group_id"] = int(group["id"])
    ended = activity["phase"] == "ended"
    return {
        "role": "student",
        "group_number": group_number,
        "phase": activity["phase"],
        "view": "results" if ended else "activity",
        "read_only": ended,
    }


def advance_activity_phase(
    connection: sqlite3.Connection, activity_code: str, target_phase: object
) -> dict:
    activity = find_activity(connection, activity_code)
    if activity is None:
        raise ActivityError("找不到此活動代碼", 404, "activity_not_found")

    expected_next = {"preparation": "active", "active": "ended"}.get(activity["phase"])
    if expected_next is None or target_phase != expected_next:
        raise ActivityError(
            "活動階段只能依準備、搶答中、已結束的順序前進",
            409,
            "invalid_phase_transition",
        )

    if activity["phase"] == "preparation":
        question_count = connection.execute(
            "SELECT COUNT(*) FROM questions WHERE activity_id = ?", (activity["id"],)
        ).fetchone()[0]
        if question_count < 1:
            raise ActivityError("開始搶答前請先匯入至少一題", 409, "questions_required")

    cursor = connection.execute(
        "UPDATE activities SET phase = ?, phase_version = phase_version + 1 "
        "WHERE id = ? AND phase = ? AND phase_version = ?",
        (target_phase, activity["id"], activity["phase"], activity["phase_version"]),
    )
    if cursor.rowcount != 1:
        connection.rollback()
        raise ActivityError("活動階段已變更，請重新整理狀態", 409, "phase_conflict")
    connection.commit()
    updated = connection.execute(
        "SELECT phase, phase_version FROM activities WHERE id = ?", (activity["id"],)
    ).fetchone()
    return {"phase": updated["phase"], "phase_version": updated["phase_version"]}


def get_activity_status(
    connection: sqlite3.Connection,
    activity_code: str,
    session_data: MutableMapping,
) -> dict:
    activity = find_activity(connection, activity_code)
    if activity is None:
        raise ActivityError("找不到此活動代碼", 404, "activity_not_found")

    status = {
        "phase": activity["phase"],
        "phase_version": activity["phase_version"],
        "role": "guest",
    }
    activity_id = int(activity["id"])
    if session_data.get("teacher_activity_id") == activity_id:
        status.update(
            {
                "role": "teacher",
                "group_count": activity["group_count"],
                "joined_groups": [
                    row["group_number"]
                    for row in connection.execute(
                        "SELECT group_number FROM groups WHERE activity_id = ? "
                        "ORDER BY group_number",
                        (activity_id,),
                    ).fetchall()
                ],
            }
        )
        return status

    group_id = session_data.get("student_group_id")
    if session_data.get("student_activity_id") == activity_id and type(group_id) is int:
        group = connection.execute(
            "SELECT group_number FROM groups WHERE id = ? AND activity_id = ?",
            (group_id, activity_id),
        ).fetchone()
        if group is not None:
            status.update({"role": "student", "group_number": group["group_number"]})
            if activity["phase"] == "ended":
                status["view"] = "results"
    return status


def import_guided_notes(
    connection: sqlite3.Connection,
    activity_id: int,
    sheet_url: str,
    sheets_adapter,
) -> dict:
    activity = connection.execute(
        "SELECT phase FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if activity is None:
        raise ActivityError("找不到此活動", 404, "activity_not_found")
    if activity["phase"] != "preparation":
        raise ActivityError("只有準備階段可匯入題目", 409, "import_phase_closed")
    if not isinstance(sheet_url, str) or not sheet_url.strip():
        raise ActivityError("請提供 Google Sheet 連結", 400, "invalid_sheet_url")

    try:
        structure = sheets_adapter.read_structure(sheet_url.strip())
        parsed = parse_guided_notes(structure)
    except SheetParseError as error:
        raise ActivityError(str(error), 400, "sheet_structure_invalid") from error
    except SheetsAdapterError as error:
        raise ActivityError(str(error), 502, "sheet_read_failed") from error
    except Exception as error:
        raise ActivityError(f"Google Sheet 讀取失敗：{error}", 502, "sheet_read_failed") from error

    snapshot_json = json.dumps(
        parsed.structure_snapshot(), ensure_ascii=False, sort_keys=True
    )
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT phase FROM activities WHERE id = ?", (activity_id,)
        ).fetchone()
        if current is None:
            raise ActivityError("找不到此活動", 404, "activity_not_found")
        if current["phase"] != "preparation":
            raise ActivityError("只有準備階段可匯入題目", 409, "import_phase_closed")

        connection.execute("DELETE FROM questions WHERE activity_id = ?", (activity_id,))
        for question in parsed.questions:
            question_id = connection.execute(
                "INSERT INTO questions (activity_id, position, question_number, answer_count) "
                "VALUES (?, ?, ?, ?)",
                (activity_id, question.position, question.question_number, len(question.blanks)),
            ).lastrowid
            for blank in question.blanks:
                connection.execute(
                    "INSERT INTO answer_cells "
                    "(question_id, position, worksheet_id, row_index, column_index, a1_address) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        question_id,
                        blank.position,
                        blank.worksheet_id,
                        blank.row_index,
                        blank.column_index,
                        blank.a1_address,
                    ),
                )
        connection.execute(
            "UPDATE activities SET source_url = ?, source_spreadsheet_id = ?, "
            "source_structure_json = ? WHERE id = ?",
            (sheet_url.strip(), parsed.spreadsheet_id, snapshot_json, activity_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return {
        "spreadsheet_id": parsed.spreadsheet_id,
        "worksheet_id": parsed.worksheet_id,
        "worksheet_title": parsed.worksheet_title,
        "question_count": len(parsed.questions),
        "questions": [
            {"question_number": question.question_number, "answer_count": len(question.blanks)}
            for question in parsed.questions
        ],
    }
