"""Verified Google Sheets export and winner-only CSV serialization."""

import csv
import io
import json
import sqlite3

from quiz_buzzer.services.activities import ActivityError
from quiz_buzzer.sheets.models import CellUpdate, SheetsAdapterError
from quiz_buzzer.sheets.parser import SheetParseError, parse_guided_notes


def export_ended_activity(
    connection: sqlite3.Connection,
    activity_id: int,
    sheets_adapter,
) -> dict:
    activity = connection.execute(
        "SELECT phase, source_url, source_spreadsheet_id, source_structure_json "
        "FROM activities WHERE id = ?",
        (activity_id,),
    ).fetchone()
    if activity is None:
        raise ActivityError("找不到此活動", 404, "activity_not_found")
    if activity["phase"] != "ended":
        raise ActivityError("只有已結束的活動可以匯出", 409, "export_phase_closed")
    if not activity["source_url"] or not activity["source_spreadsheet_id"] or not activity["source_structure_json"]:
        raise ActivityError("此活動沒有可匯出的 Guided Notes 來源", 409, "export_source_missing")

    try:
        expected = json.loads(activity["source_structure_json"])
    except (TypeError, json.JSONDecodeError) as error:
        raise ActivityError("匯入時的結構快照無法讀取，已中止匯出", 409, "export_snapshot_invalid") from error

    try:
        structure = sheets_adapter.read_structure(
            activity["source_url"], expected.get("worksheet_id")
        )
        parsed = parse_guided_notes(structure)
    except SheetParseError as error:
        raise ActivityError(
            f"匯出前重新解析失敗，工作表結構已變更：{error}",
            409,
            "export_structure_changed",
        ) from error
    except SheetsAdapterError as error:
        raise ActivityError(f"重新讀取原 Google Sheet 失敗：{error}", 502, "export_read_failed") from error
    except Exception as error:
        raise ActivityError(f"重新讀取原 Google Sheet 失敗：{error}", 502, "export_read_failed") from error

    actual = parsed.structure_snapshot()
    difference = _snapshot_difference(expected, actual, activity["source_spreadsheet_id"])
    if difference:
        raise ActivityError(f"匯出已中止：{difference}", 409, "export_structure_changed")

    winners = get_winning_submissions(connection, activity_id)
    updates: list[CellUpdate] = []
    for winner in winners:
        cells = connection.execute(
            "SELECT worksheet_id, row_index, column_index FROM answer_cells "
            "WHERE question_id = ? ORDER BY position",
            (winner["question_id"],),
        ).fetchall()
        if len(cells) != len(winner["answers"]):
            raise ActivityError(
                f"第 {winner['question_number']} 題答案格數與匯入資料不一致，已中止匯出",
                409,
                "export_local_structure_invalid",
            )
        updates.extend(
            CellUpdate(
                worksheet_id=cell["worksheet_id"],
                row_index=cell["row_index"],
                column_index=cell["column_index"],
                value=answer,
            )
            for cell, answer in zip(cells, winner["answers"], strict=True)
        )

    if updates:
        try:
            sheets_adapter.write_answers(activity["source_spreadsheet_id"], updates)
        except SheetsAdapterError as error:
            raise ActivityError(f"Google Sheet 寫入失敗：{error}", 502, "export_write_failed") from error
        except Exception as error:
            raise ActivityError(f"Google Sheet 寫入失敗：{error}", 502, "export_write_failed") from error

    return {
        "questions_written": len(winners),
        "cells_written": len(updates),
    }


def get_winning_submissions(connection: sqlite3.Connection, activity_id: int) -> list[dict]:
    """Get the earliest effective sequence per question with answers in blank order."""
    questions = connection.execute(
        "SELECT id, position, question_number FROM questions "
        "WHERE activity_id = ? ORDER BY position",
        (activity_id,),
    ).fetchall()
    winners = []
    for question in questions:
        submission = connection.execute(
            "SELECT s.id, s.group_id, g.group_number FROM submissions s "
            "JOIN groups g ON g.id = s.group_id "
            "WHERE s.question_id = ? AND s.id = ("
            "SELECT MAX(s2.id) FROM submissions s2 "
            "WHERE s2.question_id = s.question_id AND s2.group_id = s.group_id) "
            "ORDER BY s.id LIMIT 1",
            (question["id"],),
        ).fetchone()
        if submission is None:
            continue
        answers = connection.execute(
            "SELECT answer FROM submission_answers WHERE submission_id = ? ORDER BY position",
            (submission["id"],),
        ).fetchall()
        rank = connection.execute(
            "SELECT COUNT(*) + 1 FROM submissions candidate "
            "WHERE candidate.question_id = ? "
            "AND candidate.id = (SELECT MAX(s2.id) FROM submissions s2 "
            "WHERE s2.question_id = candidate.question_id AND s2.group_id = candidate.group_id) "
            "AND candidate.id < ?",
            (question["id"], submission["id"]),
        ).fetchone()[0]
        winners.append(
            {
                "question_id": question["id"],
                "question_number": question["question_number"],
                "group_number": submission["group_number"],
                "sequence": submission["id"],
                "rank": int(rank),
                "answers": [row["answer"] for row in answers],
            }
        )
    return winners


def build_winner_csv(connection: sqlite3.Connection, activity_id: int) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["題號", "組別", "答案", "搶答順位"])
    for winner in get_winning_submissions(connection, activity_id):
        for answer in winner["answers"]:
            writer.writerow(
                [
                    winner["question_number"],
                    winner["group_number"],
                    answer,
                    winner["rank"],
                ]
            )
    return "\ufeff" + output.getvalue()


def _snapshot_difference(expected: dict, actual: dict, expected_source_id: str) -> str | None:
    if expected_source_id != actual.get("spreadsheet_id"):
        return "Google Sheet 來源識別碼與匯入時不同"
    for field, label in (
        ("worksheet_id", "工作表識別碼"),
        ("worksheet_title", "工作表名稱"),
        ("header_row_index", "標題列位置"),
        ("question_column_index", "題號欄位置"),
        ("answer_column_index", "作答欄位置"),
    ):
        if expected.get(field) != actual.get(field):
            return f"{label}與匯入時不同"

    before_questions = expected.get("questions", [])
    after_questions = actual.get("questions", [])
    before_numbers = [item.get("question_number") for item in before_questions]
    after_numbers = [item.get("question_number") for item in after_questions]
    if before_numbers != after_numbers:
        return "題號或題目順序與匯入時不同"
    for before, after in zip(before_questions, after_questions, strict=True):
        number = before.get("question_number")
        if before.get("position") != after.get("position"):
            return f"第 {number} 題的題目順序與匯入時不同"
        before_blanks = before.get("blanks", [])
        after_blanks = after.get("blanks", [])
        if len(before_blanks) != len(after_blanks):
            return f"第 {number} 題的填空數與匯入時不同"
        for blank_before, blank_after in zip(before_blanks, after_blanks, strict=True):
            if blank_before != blank_after:
                return f"第 {number} 題的填空順序或儲存格位置與匯入時不同"
    if expected != actual:
        return "題目結構快照與匯入時不同"
    return None
