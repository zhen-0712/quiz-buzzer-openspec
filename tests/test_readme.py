import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_documents_network_access_and_local_data():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "python run.py" in readme
    assert "--host" in readme
    assert "ipconfig" in readme
    assert "0.0.0.0" in readme
    assert "不提供公網部署承諾" in readme
    assert "instance/quiz-buzzer.sqlite3" in readme
    assert "假的 Google Sheets adapter" in readme


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
