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

## Guided Notes 工作表選擇

系統一律依試算表中的分頁順序略過沒有同一列「題號」與「作答」標題的說明頁，並採用第一個同時有兩個標題的工作表；網址中的 `gid` 不影響選頁。選定後若題號或填空有歧義、該頁有多組標題列，或同一題號在另一個非相鄰題號區塊再次出現，匯入會指出工作表與位置並失敗，不會改用後面的工作表。題號合併跨越多列仍視為同一題組。

匯出會依匯入時保存的工作表 ID 重新讀取該頁；新增或修改其他分頁不會改變匯出目標。

真實多工作表人工驗證由使用者執行：建立第一頁無標題的說明頁、第二頁為 Guided Notes；不論連結是否帶 `gid`，匯入都應採用第二頁。複製一份並把題號改成非相鄰重複，確認匯入被拒且活動未變更。匯入後可在匯出前插入列，或讓另一頁也有標題並調整分頁順序，確認匯出整份中止、零寫入並列出所有問題題號；未改動時確認答案仍寫入匯入時的工作表。真實 Google 驗證不得由自動化測試執行。

## 匯出結果

活動結束後，老師在活動頁按「匯出到 Google Sheet」。匯出前先備份原試算表，並在確認提示中確認已備份；系統會重新讀取 Sheet，確認題號、填空數、順序與儲存格位置仍與匯入時相同，再把各題勝出組的答案以純文字寫回原作答格。任何結構差異或雲端讀寫錯誤都會中止並顯示原因；可在修正後再次匯出，重複匯出會以最新勝出答案覆寫作答格。

活動結束後，只有老師可按「下載 CSV」。CSV 使用 UTF-8 BOM、CRLF 換行，欄位為「題號、組別、填空序號、答案、搶答順位」；題組的每個填空各佔一列，填空序號從 1 起算，同題各列組別與順位相同，無人作答的題目不列。CSV 只包含勝出組答案。答案欄若以 `=`, `+`, `-`, `@` 或 Tab、CR、LF 開頭會加單引號前綴，避免 Excel 將其當公式執行；Excel 開啟時此前綴會顯示出來，這是刻意設計。前綴僅作用於 CSV 答案欄，再依 RFC 4180 跳脫逗號與雙引號；其他欄位不加前綴，寫回 Google Sheet 時仍以原答案作為純文字，不加前綴。

若匯出時重新解析本身失敗（`SheetParseError`），只回報 parser 的第一個錯誤位置，不彙整其他題號；「列出全部問題題號」只適用於可解析、但與匯入快照結構不同的情況。

老師活動結束後的提交表格只顯示每組每題最新有效答案與順位，不顯示已被重送取代的舊答案；本機資料庫仍保留提交歷史。

老師在「搶答中」的即時作答狀況預設收起，按「顯示作答狀況」才展開；輪詢更新會保留展開狀態，重新整理後回到收起，活動結束時自動展開。收起時頁面 DOM 不含組別作答資料。此功能只保證投影畫面與 DOM 不含資料，老師 API 本身仍回傳監看資料，需由老師確認投影與分享方式。

## 執行自動化測試

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
```

**執行 `pytest` 前必須先啟用 `.venv`（PowerShell：`.\.venv\Scripts\Activate.ps1`），否則測試收集時會因缺少 `openpyxl` 而失敗。**

安裝和測試均使用 `requirements-dev.txt`；它包含應用程式的 `requirements.txt`、pytest 與測試範本所需的 openpyxl。自動化測試使用本機暫存資料庫與假的 Google Sheets adapter，不需要 Google 憑證，也不會連線 Google。啟用虛擬環境後，直接執行 `pytest` 也可運作；標準測試指令是 `python -m pytest`。

### 學生作答草稿與重送手動驗證

目前 pytest 沒有瀏覽器 JavaScript 執行器，請用瀏覽器完成互動驗證：

1. 老師建立活動並匯入至少兩題的 Guided Notes，學生加入後開始搶答。
2. 學生在第 1 題和第 2 題輸入不同草稿，等待數秒讓頁面輪詢重畫；確認兩題草稿都保留。
3. 完整送出第 1 題；確認送出完成後按鈕重新可按、第 1 題輸入框清空、第 2 題草稿仍保留。再次送出第 1 題也應可操作。
4. 在第 1 題輸入一組新草稿，使用瀏覽器開發者工具暫時切換離線後送出，再恢復連線；確認顯示失敗訊息、按鈕恢復可按，且第 1、2 題草稿都保留。

### 老師投影作答狀況手動驗證

1. 老師登入並開始搶答；確認「即時監看」預設收起。
2. 使用開發者工具檢查收起狀態的 DOM，確認沒有各題作答組數、提交清單、組別、答案或順位。
3. 按「顯示作答狀況」展開，讓學生提交並等待輪詢更新；確認仍保持展開並顯示新資料。再次按鈕收起後重查 DOM。
4. 重新整理老師頁面，確認回到預設收起；結束活動後確認結果自動展開。

## 已知限制

- 系統以單機本機程序和 SQLite 為目標，資料存放在啟動主機；不提供公網部署承諾。
- 同一組多人共用同一組別身分，系統不辨識組內個別學生。
- 區網連線依賴主機網路與防火牆設定；跨裝置連線需人工驗證。
- Google Sheets 自動化測試使用假 adapter；真實 OAuth、雲端讀寫與權限需由使用者使用自建憑證人工驗證。
