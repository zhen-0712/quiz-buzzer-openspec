import subprocess


def test_local_secrets_and_database_paths_are_ignored():
    candidates = [
        "instance/google-oauth-client.json",
        "instance/token.json",
        "instance/quiz-buzzer.sqlite3",
        "instance/quiz-buzzer.sqlite3-wal",
        ".credentials/client.pem",
        "credentials/local.key",
        ".env",
    ]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        input=("\n".join(candidates) + "\n").encode(),
        check=True,
        capture_output=True,
    )

    ignored = set(result.stdout.decode().splitlines())
    assert ignored == set(candidates)
