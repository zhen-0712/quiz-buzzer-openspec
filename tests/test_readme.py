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
    assert "python -m pip install -r requirements-dev.txt" in readme
    assert "python -m pytest" in readme
    assert "quiz_buzzer/" in readme and "templates/" in readme
    assert "tests/" in readme and "fixtures/" in readme
    assert "用瀏覽器模擬老師與學生" in readme
    assert "不同瀏覽器或隔離的瀏覽器設定檔" in readme
    assert "同一組多人共用同一組別身分" in readme


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
        "**下載後必須將 JSON 重新命名為 `client_secret.json`**",
        "instance/token.json",
        "分享給剛才授權的同一 Google 帳戶",
    ]
    assert all(step in readme for step in required_steps)
    assert "-----BEGIN PRIVATE KEY-----" not in readme
    assert '"private_key"' not in readme
    assert '"client_id"' not in readme


def test_readme_documents_export_backup_and_csv_row_convention():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "匯出前先備份原試算表" in readme
    assert "重新讀取 Sheet" in readme
    assert "UTF-8 BOM" in readme
    assert "每個填空各佔一列" in readme
    assert "只包含各題勝出組的答案" in readme


def test_readme_documents_sheet_selection_latest_results_and_student_draft_check():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for phrase in (
        "第一個同時有兩個標題的工作表",
        "網址片段 `#gid=<工作表 ID>`",
        "不會改用後面的工作表",
        "匯入時選定的工作表 ID",
        "非相鄰題號區塊再次出現",
        "每組每題最新有效答案",
        "學生作答草稿與重送手動驗證",
        "開發者工具暫時切換離線",
    ):
        assert phrase in readme


def test_acceptance_matrix_maps_align_and_fix_regressions():
    matrix = (ROOT / "docs" / "acceptance-matrix.md").read_text(encoding="utf-8")

    for test_name in (
        "test_parser_skips_headerless_sheets_and_uses_first_matching_sheet",
        "test_parser_rejects_non_adjacent_repeated_question_number_with_both_locations",
        "test_google_adapter_reads_all_worksheets_when_no_gid_is_selected",
        "test_import_with_gid_without_headers_does_not_scan_other_worksheets",
        "test_identical_resubmission_gets_new_sequence_and_changes_rank",
        "test_export_rechecks_only_the_worksheet_recorded_at_import",
        "test_student_script_captures_drafts_and_reenables_the_current_form",
    ):
        assert test_name in matrix


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
