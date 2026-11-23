"""JSON endpoints for the activity lifecycle."""

from flask import Blueprint, current_app, jsonify, request, session

from quiz_buzzer.data.database import get_db
from quiz_buzzer.services.activities import (
    ActivityError,
    advance_activity_phase,
    create_activity,
    get_activity_status,
    find_activity,
    import_guided_notes,
    join_activity,
    login_teacher,
)
from quiz_buzzer.sheets.google_adapter import GoogleSheetsAdapter
from quiz_buzzer.services.submissions import get_quiz_view, submit_question


bp = Blueprint("api", __name__, url_prefix="/api")


def _error(error: ActivityError):
    return jsonify({"error": error.error_code, "message": str(error)}), error.status_code


@bp.post("/activities")
def create_activity_route():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_request", "message": "請提供活動設定"}), 400
    try:
        activity_id, code = create_activity(
            get_db(), payload.get("group_count"), payload.get("password")
        )
    except ActivityError as error:
        return _error(error)
    session.clear()
    session["teacher_activity_id"] = activity_id
    return jsonify({"activity_code": code, "phase": "preparation"}), 201


@bp.post("/activities/<activity_code>/teacher-login")
def teacher_login_route(activity_code: str):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_request", "message": "請輸入活動密碼"}), 400
    try:
        activity_id = login_teacher(
            get_db(), activity_code, payload.get("password"), session
        )
    except ActivityError as error:
        return _error(error)
    return jsonify({"role": "teacher", "activity_id": activity_id}), 200


@bp.post("/activities/<activity_code>/join")
def join_activity_route(activity_code: str):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_request", "message": "請選擇組別編號"}), 400
    try:
        result = join_activity(
            get_db(), activity_code, payload.get("group_number"), session
        )
    except ActivityError as error:
        return _error(error)
    return jsonify(result), 200


@bp.post("/activities/<activity_code>/phase")
def advance_phase_route(activity_code: str):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_request", "message": "請指定下一階段"}), 400
    activity = find_activity(get_db(), activity_code)
    if activity is None:
        return _error(ActivityError("找不到此活動代碼", 404, "activity_not_found"))
    if session.get("teacher_activity_id") != activity["id"]:
        return _error(ActivityError("只有已驗證的老師可切換階段", 403, "teacher_required"))
    try:
        result = advance_activity_phase(
            get_db(), activity_code, payload.get("phase")
        )
    except ActivityError as error:
        return _error(error)
    return jsonify(result), 200


@bp.get("/activities/<activity_code>/status")
def activity_status_route(activity_code: str):
    try:
        result = get_activity_status(get_db(), activity_code, session)
    except ActivityError as error:
        return _error(error)
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/activities/<activity_code>/import")
def import_questions_route(activity_code: str):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_request", "message": "請提供 Google Sheet 連結"}), 400
    activity = find_activity(get_db(), activity_code)
    if activity is None:
        return _error(ActivityError("找不到此活動代碼", 404, "activity_not_found"))
    if session.get("teacher_activity_id") != activity["id"]:
        return _error(ActivityError("只有已驗證的老師可匯入題目", 403, "teacher_required"))
    if activity["phase"] != "preparation":
        return _error(ActivityError("只有準備階段可匯入題目", 409, "import_phase_closed"))

    adapter = current_app.config.get("SHEETS_ADAPTER")
    if adapter is None:
        try:
            adapter = GoogleSheetsAdapter.from_user_credentials(current_app.instance_path)
        except Exception as error:
            return _error(ActivityError(str(error), 400, "sheets_credentials_unavailable"))
    try:
        result = import_guided_notes(
            get_db(), activity["id"], payload.get("sheet_url"), adapter
        )
    except ActivityError as error:
        return _error(error)
    return jsonify(result), 200


@bp.post("/activities/<activity_code>/submissions")
def submit_question_route(activity_code: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_request", "message": "請提供題號與整題答案"}), 400
    activity = find_activity(get_db(), activity_code)
    if activity is None:
        return _error(ActivityError("找不到此活動代碼", 404, "activity_not_found"))
    group_id = session.get("student_group_id")
    if (
        session.get("student_activity_id") != activity["id"]
        or type(group_id) is not int
    ):
        return _error(ActivityError("只有已加入活動的學生可提交答案", 403, "student_required"))
    question_number = payload.get("question_number")
    if not isinstance(question_number, str) or not question_number.strip():
        return _error(ActivityError("請提供題號", 400, "invalid_question_number"))
    try:
        result = submit_question(
            get_db(), activity_code, group_id, question_number.strip(), payload.get("answers")
        )
    except ActivityError as error:
        return _error(error)
    return jsonify(result), 201


@bp.get("/activities/<activity_code>/quiz")
def quiz_view_route(activity_code: str):
    try:
        result = get_quiz_view(get_db(), activity_code, session)
    except ActivityError as error:
        return _error(error)
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response
