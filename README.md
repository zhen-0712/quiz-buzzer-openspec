# 課堂搶答系統

本專案使用 Flask 提供本機網頁服務，並以 SQLite 保存活動資料。系統目前仍在開發中。

## 安裝

需要 Python 3.10 或更新版本。於 repo 根目錄執行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` 會安裝 `requirements.txt` 的應用相依套件，並包含讀取測試範本 xlsx 所需的 openpyxl。

## 專案結構

```text
quiz_buzzer/                 Flask 應用程式
  routes/                    HTML 與 JSON API 路由
  services/                  活動、提交、順位與匯出邏輯
  data/                      SQLite schema 與連線
  sheets/                    Sheets 介面、Google adapter、Guided Notes parser
  templates/                 Jinja HTML 頁面
  static/                    原生 JavaScript 與 CSS
tests/                       自動化測試
  fixtures/                  課程提供的 xlsx 範本
scripts/                     本機輔助指令
docs/                        驗收情境對照表
openspec/                    變更提案、規格與任務
requirements.txt             執行應用程式所需套件
requirements-dev.txt         執行及測試環境套件（包含 requirements.txt）
run.py                       Flask 啟動入口
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

## 用瀏覽器模擬老師與學生

啟動伺服器後，老師在瀏覽器開啟 `http://127.0.0.1:5000` 並建立活動；學生在另一個瀏覽器視窗輸入活動代碼和組別編號加入。要在同一台電腦模擬多個角色或多組，請為每個角色／組別使用不同瀏覽器或隔離的瀏覽器設定檔，避免共用登入 cookie。老師重新整理後可沿用登入狀態；換瀏覽器時，回首頁輸入活動代碼與密碼重新登入。

搶答中頁面每秒向伺服器同步階段與角色允許檢視的資料。學生可選題並一次送出該題所有填空；結束後可檢視勝出結果與本組順位。

## 使用者自建 Google Sheets 憑證

每位使用者以自己的 Google 帳戶和 Google Cloud 專案建立 OAuth 憑證；本 repo 不提供共用金鑰、用戶端憑證或存取 token。

1. 在 Google Cloud Console 建立自己的 Cloud 專案。
2. 在該專案的 API Library 啟用 Google Sheets API。
3. 設定 OAuth 同意畫面／Google Auth Platform，填妥應用程式資訊；若應用程式處於測試模式，將自己用來授權的 Google 帳戶加入測試使用者。
4. 建立 OAuth 用戶端，應用程式類型選「電腦版應用程式（Desktop app）」，下載該用戶端的 JSON 檔。
5. 在 repo 根目錄建立 `instance/`（如尚不存在）；**下載後必須將 JSON 重新命名為 `client_secret.json`**，再放入 `instance/client_secret.json`。`instance/` 已被 `.gitignore` 排除，請勿提交 JSON 或 `instance/token.json`。找不到憑證時，系統會提示憑證檔名必須是 `client_secret.json`。
6. 將要匯入及匯出的 Google Sheet 分享給剛才授權的同一 Google 帳戶，並授予編輯者權限。

首次讀取 Sheet 時，系統會使用這份使用者自建的 Desktop OAuth 用戶端要求帳戶授權；授權後的 token 僅存放在 `instance/token.json`。自動化測試使用假 Sheets adapter，不需要建立 Cloud 專案、不會讀取這些檔案，也不會啟動 OAuth 授權流程。

## 匯出結果

活動結束後，老師在活動頁按「匯出到 Google Sheet」。匯出前先備份原試算表，並在確認提示中確認已備份；系統會重新讀取 Sheet，確認題號、填空數、順序與儲存格位置仍與匯入時相同，再把各題勝出組的答案以純文字寫回原作答格。任何結構差異或雲端讀寫錯誤都會中止並顯示原因；可在修正後再次匯出，重複匯出會以最新勝出答案覆寫作答格。

活動結束後，老師也可按「下載 CSV」。CSV 使用 UTF-8 BOM，欄位為題號、組別、答案、搶答順位；題組的每個填空各佔一列，題號、組別和順位會在各列重複。CSV 只包含各題勝出組的答案。

## 執行自動化測試

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
```

安裝和測試均使用 `requirements-dev.txt`；它包含應用程式的 `requirements.txt`、pytest 與測試範本所需的 openpyxl。自動化測試使用本機暫存資料庫與假的 Google Sheets adapter，不需要 Google 憑證，也不會連線 Google。啟用虛擬環境後，直接執行 `pytest` 也可運作；標準測試指令是 `python -m pytest`。

## 已知限制

- 系統以單機本機程序和 SQLite 為目標，資料存放在啟動主機；不提供公網部署承諾。
- 同一組多人共用同一組別身分，系統不辨識組內個別學生。
- 區網連線依賴主機網路與防火牆設定；跨裝置連線需人工驗證。
- Google Sheets 自動化測試使用假 adapter；真實 OAuth、雲端讀寫與權限需由使用者使用自建憑證人工驗證。
