"""Default configuration for local and test application instances."""

import os
import secrets

from flask import Flask


def configure_app(app: Flask) -> None:
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("QUIZ_BUZZER_SESSION_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get("QUIZ_BUZZER_DATABASE")
        or os.path.join(app.instance_path, "quiz-buzzer.sqlite3"),
    )
