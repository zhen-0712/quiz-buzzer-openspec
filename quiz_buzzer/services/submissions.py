"""Question submissions, server sequencing, ranking, and role-scoped views."""

import sqlite3
from collections.abc import MutableMapping

from quiz_buzzer.services.activities import ActivityError, find_activity


def submit_question(
    connection: sqlite3.Connection,
    activity_code: str,
    group_id: int,
    question_number: str,
    answers: object,
) -> dict:
    """Accept one complete answer set and atomically assign its sequence."""
    if not isinstance(answers, list):
        raise ActivityError("答案必須以清單一次送出", 400, "invalid_answers")
    if any(not isinstance(answer, str) for answer in answers):
        raise ActivityError("每個答案都必須是文字", 400, "invalid_answers")
    normalized = [answer.strip() for answer in answers]
    if any(not answer for answer in normalized):
        raise ActivityError("每個填空都必須提供非空答案", 400, "blank_answer")
    if any(len(answer) > 200 for answer in normalized):
        raise ActivityError("每個答案不得超過 200 字", 400, "answer_too_long")

    try:
        connection.execute("BEGIN IMMEDIATE")
        activity = find_activity(connection, activity_code)
        if activity is None:
            raise ActivityError("找不到此活動代碼", 404, "activity_not_found")
        if activity["phase"] != "active":
            raise ActivityError("只有搶答中可提交答案", 409, "submission_phase_closed")
        group = connection.execute(
            "SELECT id FROM groups WHERE id = ? AND activity_id = ?",
            (group_id, activity["id"]),
        ).fetchone()
        if group is None:
            raise ActivityError("學生組別不屬於此活動", 403, "student_required")
        question = connection.execute(
            "SELECT id, answer_count FROM questions "
            "WHERE activity_id = ? AND question_number = ?",
            (activity["id"], question_number),
        ).fetchone()
        if question is None:
            raise ActivityError("找不到此題號", 404, "question_not_found")
        if len(normalized) != question["answer_count"]:
            raise ActivityError(
                f"本題需提交 {question['answer_count']} 個答案",
                400,
                "answer_count_mismatch",
            )

        submission_id = connection.execute(
            "INSERT INTO submissions (question_id, group_id) VALUES (?, ?)",
            (question["id"], group_id),
        ).lastrowid
        connection.executemany(
            "INSERT INTO submission_answers (submission_id, position, answer) "
            "VALUES (?, ?, ?)",
            [
                (submission_id, position, answer)
                for position, answer in enumerate(normalized)
            ],
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    ranked = _question_submissions(connection, int(question["id"]))
    current = next(item for item in ranked if item["group_id"] == group_id)
    return {
        "question_number": question_number,
        "answers": normalized,
        "sequence": int(submission_id),
        "rank": current["rank"],
    }


def get_quiz_view(
    connection: sqlite3.Connection,
    activity_code: str,
    session_data: MutableMapping,
) -> dict:
    """Return only information permitted for this activity, role, and phase."""
    activity = find_activity(connection, activity_code)
    if activity is None:
        raise ActivityError("找不到此活動代碼", 404, "activity_not_found")
    activity_id = int(activity["id"])
    is_teacher = session_data.get("teacher_activity_id") == activity_id
    student_group_id = session_data.get("student_group_id")
    is_student = session_data.get("student_activity_id") == activity_id and type(
        student_group_id
    ) is int
    if not is_teacher and not is_student:
        raise ActivityError("請先以老師或學生身分進入活動", 403, "activity_access_required")

    group_number = None
    if is_student:
        group = connection.execute(
            "SELECT group_number FROM groups WHERE id = ? AND activity_id = ?",
            (student_group_id, activity_id),
        ).fetchone()
        if group is None:
            raise ActivityError("學生組別不屬於此活動", 403, "student_required")
        group_number = int(group["group_number"])

    questions = connection.execute(
        "SELECT id, question_number, answer_count FROM questions "
        "WHERE activity_id = ? ORDER BY position",
        (activity_id,),
    ).fetchall()
    role = "teacher" if is_teacher else "student"
    response = {"role": role, "phase": activity["phase"]}

    if activity["phase"] == "preparation":
        response["questions"] = [] if is_student else _question_summaries(questions)
        if is_student:
            response["submissions"] = []
        return response

    if activity["phase"] == "active":
        response["questions"] = _question_summaries(questions)
        all_rows = _all_submission_views(connection, activity_id)
        if is_teacher:
            response["submissions"] = all_rows
            response["current_submissions"] = [
                row for row in all_rows if row["is_effective"]
            ]
        else:
            response["group_number"] = group_number
            response["submissions"] = [
                {
                    "question_number": row["question_number"],
                    "answers": row["answers"],
                    "status": "已送出",
                }
                for row in all_rows
                if row["group_number"] == group_number and row["is_effective"]
            ]
        return response

    all_rows = _all_submission_views(connection, activity_id)
    if is_teacher:
        response["questions"] = _question_summaries(questions)
        response["submissions"] = all_rows
        response["current_submissions"] = [
            row for row in all_rows if row["is_effective"]
        ]
        return response

    response["group_number"] = group_number
    response["results"] = []
    for question in questions:
        rows = [
            row
            for row in all_rows
            if row["question_number"] == question["question_number"]
            and row["is_effective"]
        ]
        winner = min(rows, key=lambda row: row["sequence"]) if rows else None
        own = next(
            (row for row in rows if row["group_number"] == group_number), None
        )
        response["results"].append(
            {
                "question_number": question["question_number"],
                "winner": _public_submission(winner) if winner else None,
                "own": _public_submission(own) if own else None,
            }
        )
    return response


def _question_summaries(questions) -> list[dict]:
    return [
        {
            "question_number": question["question_number"],
            "answer_count": question["answer_count"],
        }
        for question in questions
    ]


def _all_submission_views(connection: sqlite3.Connection, activity_id: int) -> list[dict]:
    rows = connection.execute(
        "SELECT q.id AS question_id, q.question_number, g.group_number, "
        "s.id AS sequence, s.accepted_at, a.position, a.answer "
        "FROM submissions s "
        "JOIN questions q ON q.id = s.question_id "
        "JOIN groups g ON g.id = s.group_id "
        "JOIN submission_answers a ON a.submission_id = s.id "
        "WHERE q.activity_id = ? "
        "ORDER BY q.position, g.group_number, s.id, a.position",
        (activity_id,),
    ).fetchall()
    history: list[dict] = []
    for row in rows:
        key = (row["question_id"], row["group_number"], row["sequence"])
        if not history or history[-1]["_key"] != key:
            history.append(
                {
                    "_key": key,
                    "question_number": row["question_number"],
                    "group_number": row["group_number"],
                    "sequence": row["sequence"],
                    "accepted_at": row["accepted_at"],
                    "answers": [],
                    "is_effective": False,
                    "rank": None,
                }
            )
        history[-1]["answers"].append(row["answer"])

    latest_by_group: dict[tuple[int, int], dict] = {}
    for item in history:
        key = (item["_key"][0], item["group_number"])
        if key not in latest_by_group or item["sequence"] > latest_by_group[key]["sequence"]:
            latest_by_group[key] = item
    by_question: dict[int, list[dict]] = {}
    for (question_id, _group_number), item in latest_by_group.items():
        by_question.setdefault(question_id, []).append(item)
    for effective in by_question.values():
        for rank, item in enumerate(sorted(effective, key=lambda value: value["sequence"]), start=1):
            item["is_effective"] = True
            item["rank"] = rank

    for item in history:
        item.pop("_key")
    return history


def _question_submissions(connection: sqlite3.Connection, question_id: int) -> list[dict]:
    rows = connection.execute(
        "SELECT s.id AS sequence, s.group_id, g.group_number "
        "FROM submissions s JOIN groups g ON g.id = s.group_id "
        "WHERE s.question_id = ? AND s.id = ("
        "SELECT MAX(s2.id) FROM submissions s2 "
        "WHERE s2.question_id = s.question_id AND s2.group_id = s.group_id) "
        "ORDER BY s.id",
        (question_id,),
    ).fetchall()
    return [
        {"group_id": row["group_id"], "group_number": row["group_number"], "sequence": row["sequence"], "rank": rank}
        for rank, row in enumerate(rows, start=1)
    ]


def _public_submission(item: dict) -> dict:
    return {
        "group_number": item["group_number"],
        "answers": item["answers"],
        "rank": item["rank"],
    }
