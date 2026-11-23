import sqlite3

from quiz_buzzer.data.database import BUSY_TIMEOUT_MS, SCHEMA_VERSION, connect, init_db


def test_schema_initializes_and_persists_across_connections(tmp_path):
    database_path = str(tmp_path / "persistent.sqlite3")
    first = connect(database_path)
    init_db(first)
    first.execute(
        "INSERT INTO activities (code, password_hash, group_count) VALUES (?, ?, ?)",
        ("ABC123", "test-hash", 4),
    )
    first.commit()
    first.close()

    reopened = connect(database_path)
    row = reopened.execute("SELECT code, group_count FROM activities").fetchone()

    assert row["code"] == "ABC123"
    assert row["group_count"] == 4
    assert reopened.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    reopened.close()


def test_database_enables_wal_foreign_keys_and_busy_timeout(tmp_path):
    connection = connect(str(tmp_path / "settings.sqlite3"))

    journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert busy_timeout == BUSY_TIMEOUT_MS
    assert foreign_keys == 1
    connection.close()


def test_database_rejects_a_newer_schema_version(tmp_path):
    connection = connect(str(tmp_path / "future.sqlite3"))
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")

    try:
        init_db(connection)
    except RuntimeError as error:
        assert "newer than supported" in str(error)
    else:
        raise AssertionError("newer schema version should have been rejected")
    finally:
        connection.close()


def test_database_uses_sqlite_connections(tmp_path):
    connection = connect(str(tmp_path / "type.sqlite3"))
    assert isinstance(connection, sqlite3.Connection)
    connection.close()
