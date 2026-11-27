import subprocess


def test_local_secrets_and_database_paths_are_ignored():
    candidates = [
        "instance/google-oauth-client.json",
        "instance/token.json",
        "instance/quiz-buzzer.sqlite3",
        "instance/quiz-buzzer.sqlite3-wal",
        "貼上視窗 A 的資料庫路徑",
        ".credentials/client.pem",
        "credentials/local.key",
        ".env",
    ]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-z", "--stdin"],
        input=("\0".join(candidates) + "\0").encode(),
        check=True,
        capture_output=True,
    )

    ignored = set(result.stdout.decode().split("\0")) - {""}
    assert ignored == set(candidates)
