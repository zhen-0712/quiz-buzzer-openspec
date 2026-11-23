# 課堂搶答系統

本專案使用 Flask 提供本機網頁服務，並以 SQLite 保存活動資料。系統目前仍在開發中。

## 安裝

需要 Python 3.10 或更新版本。於 repo 根目錄執行：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 啟動

預設監聽所有網路介面，使用 TCP port 5000：

```powershell
python run.py
```

可用 `--host` 指定監聽介面，並用 `--port` 指定 port：

```powershell
python run.py --host 127.0.0.1 --port 5000
```

要讓同一區域網路的學生連入，老師可在 Windows 執行 `ipconfig`，找到目前使用的 Wi-Fi 或乙太網路介面之 IPv4 位址。學生使用同一區域網路，在瀏覽器開啟 `http://<老師的區網 IPv4 位址>:5000`。例如將 `<老師的區網 IPv4 位址>` 換成該介面顯示的位址；不要使用 `127.0.0.1`，因為那是學生裝置自己的回送位址。

預設 `0.0.0.0` 會允許可連到老師電腦的網路裝置嘗試連線。請只在可信任的本機區網使用；本專案不提供公網部署承諾。

## 本機資料與備份

SQLite 資料庫預設放在 `instance/quiz-buzzer.sqlite3`。也可用環境變數 `QUIZ_BUZZER_DATABASE` 指定其他本機資料庫路徑。`instance/`、資料庫與 SQLite WAL 暫存檔已由 `.gitignore` 排除，不應提交到版本庫。

備份前先正常停止系統，待程序結束後複製資料庫檔案到安全位置。恢復時先停止系統，再將備份檔放回資料庫路徑。

## 執行自動化測試

```powershell
pytest
```

自動化測試使用本機暫存資料庫與假的 Google Sheets adapter，不需要 Google 憑證，也不會連線 Google。

安裝步驟中的 `python -m pip install -r requirements.txt` 會一併安裝 pytest。請在啟用 `.venv` 後執行 `pytest`；`pytest.ini` 已設定專案根目錄匯入路徑，因此直接執行 pytest 與 `python -m pytest` 都可載入 `quiz_buzzer`。
