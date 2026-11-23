"""Flask application factory for the classroom quiz buzzer."""

import os

from flask import Flask

from quiz_buzzer.config import configure_app
from quiz_buzzer.data.database import init_app as init_database
from quiz_buzzer.routes.pages import bp as pages_blueprint


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    configure_app(app)
    if test_config:
        app.config.update(test_config)
    app.register_blueprint(pages_blueprint)
    init_database(app)

    return app
