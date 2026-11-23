import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_documents_network_access_and_local_data():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "python run.py" in readme
    assert "python -m pip install -r requirements-dev.txt" in readme
    assert "--host" in readme
    assert "ipconfig" in readme
    assert "0.0.0.0" in readme
    assert "不提供公網部署承諾" in readme
    assert "instance/quiz-buzzer.sqlite3" in readme
    assert "假的 Google Sheets adapter" in readme


def test_readme_documents_user_created_google_oauth_setup_without_credentials():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    required_steps = [
        "使用者自建",
        "Google Cloud Console 建立自己的 Cloud 專案",
        "啟用 Google Sheets API",
        "OAuth 同意畫面",
        "測試使用者",
        "電腦版應用程式（Desktop app）",
        "instance/client_secret.json",
        "instance/token.json",
        "分享給剛才授權的同一 Google 帳戶",
    ]
    assert all(step in readme for step in required_steps)
    assert "-----BEGIN PRIVATE KEY-----" not in readme
    assert '"private_key"' not in readme
    assert '"client_id"' not in readme


def test_documented_entrypoint_help_runs():
    result = subprocess.run(
        [sys.executable, "run.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    assert "--host" in result.stdout
    assert "--port" in result.stdout
