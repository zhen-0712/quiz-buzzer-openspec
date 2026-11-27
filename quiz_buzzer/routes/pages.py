"""HTML page routes."""

from flask import Blueprint, abort, make_response, render_template

from quiz_buzzer.data.database import get_db
from quiz_buzzer.services.activities import find_activity


bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/activities/<activity_code>/status")
def activity_status_page(activity_code: str):
    activity = find_activity(get_db(), activity_code)
    if activity is None:
        abort(404)
    phase_labels = {
        "preparation": "準備",
        "active": "搶答中",
        "ended": "已結束",
    }
    response = make_response(render_template(
        "activity_status.html",
        activity_code=activity["code"],
        phase=activity["phase"],
        phase_label=phase_labels[activity["phase"]],
    ))
    response.headers["Cache-Control"] = "no-store"
    return response
