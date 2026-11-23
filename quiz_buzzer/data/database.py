"""SQLite connection management and initial schema."""

import sqlite3
from pathlib import Path

from flask import current_app, g


SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 5_000

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    group_count INTEGER NOT NULL CHECK (group_count BETWEEN 1 AND 100),
    phase TEXT NOT NULL DEFAULT 'preparation'
        CHECK (phase IN ('preparation', 'active', 'ended')),
    phase_version INTEGER NOT NULL DEFAULT 0 CHECK (phase_version >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_url TEXT,
    source_spreadsheet_id TEXT,
    source_structure_json TEXT
);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY,
    activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    group_number INTEGER NOT NULL CHECK (group_number BETWEEN 1 AND 100),
    UNIQUE (activity_id, group_number)
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position >= 0),
    question_number TEXT NOT NULL,
    answer_count INTEGER NOT NULL CHECK (answer_count >= 1),
    UNIQUE (activity_id, position),
    UNIQUE (activity_id, question_number)
);

CREATE TABLE IF NOT EXISTS answer_cells (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position >= 0),
    worksheet_id TEXT NOT NULL,
    row_index INTEGER NOT NULL CHECK (row_index >= 0),
    column_index INTEGER NOT NULL CHECK (column_index >= 0),
    a1_address TEXT NOT NULL,
    UNIQUE (question_id, position)
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS submissions_question_group_sequence
    ON submissions(question_id, group_id, id DESC);

CREATE TABLE IF NOT EXISTS submission_answers (
    submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position >= 0),
    answer TEXT NOT NULL,
    PRIMARY KEY (submission_id, position)
);
"""


def connect(database_path: str) -> sqlite3.Connection:
    """Open a configured SQLite connection for the given local database."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        str(path),
        timeout=BUSY_TIMEOUT_MS / 1_000,
        isolation_level="DEFERRED",
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def get_db() -> sqlite3.Connection:
    """Return the request-scoped SQLite connection."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db(connection: sqlite3.Connection) -> None:
    """Create the initial schema or reject a database from a newer version."""
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema version {version} is newer than supported version {SCHEMA_VERSION}"
        )
    connection.executescript(SCHEMA_SQL)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    connection.commit()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db(get_db())
