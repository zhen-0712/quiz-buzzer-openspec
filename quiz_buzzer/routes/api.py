"""JSON endpoints for the activity lifecycle."""

from flask import Blueprint, current_app, jsonify, request, session

from quiz_buzzer.data.database import get_db
from quiz_buzzer.services.activities import (
    ActivityError,
    advance_activity_phase,
    create_activity,
    get_activity_status,
    find_activity,
    join_activity,
    login_teacher,
)


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
