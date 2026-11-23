# Proposal

## Why

課堂搶答需要同時處理題目匯入、分組作答、可追溯順位與課後回寫；以人工記錄容易出現順位爭議，也難以把結果整理回 Guided Notes。此提案定義一套可在教師本機執行的完整流程，並確保 Google Sheets 存取可由假實作測試。

## What Changes

- 新增老師建立活動、設定密碼與組數、控制單向階段，以及學生依活動代碼和組別加入／重新進入的流程。
- 新增從線上 Google Sheet 動態解析題號、作答欄與合併儲存格的匯入流程，題數由解析結果決定。
- 新增整題提交、伺服器序號順位、老師即時監看，以及依階段限制學生可見結果的行為。
- 新增活動結束後重新解析來源 Sheet、確認結構一致，再將成功組答案以純文字寫回的匯出流程。
- 以本機持久化保存活動與順位；以 Google Sheets 存取介面隔離官方 API 與假實作。
- Flask 啟動 host 預設為 `0.0.0.0` 並提供 `--host` 設定，支援教師在本機區網提供學生連入；不承諾公網部署支援。
- 規劃 Flask、HTML/JS、README、`.gitignore` 檢查與自動化測試；真實 Google 憑證與雲端串接列為人工驗證。

## Capabilities

### New Capabilities
- `activity-lifecycle`: 活動建立、老師驗證、組別加入、階段轉換、同步與本機恢復。
- `guided-notes-import`: Google Sheet 結構解析、題目匯入與明確錯誤回報。
- `quiz-buzzer`: 整題作答、重送、順位、搶答中監看及依角色和階段提供結果。
- `sheets-export`: 匯出前重新解析與比對結構，並將成功組答案寫回來源 Sheet。

### Modified Capabilities

無。此 repo 尚無既有 OpenSpec 能力規格。

## Impact

- 新增 Python Flask 本機應用、HTML/JS 頁面、持久化資料層及 Google Sheets adapter。
- 新增 Google 官方 API Python 套件；自動化測試使用假的 Sheets adapter，不連外部 Google 服務。
- 新增 OpenSpec 能力規格、測試、README 憑證建立說明，並檢查 `.gitignore` 排除使用者憑證與本機資料。
- 影響使用者本機的 Google OAuth 憑證、Google Sheet 權限及匯出目標儲存格；真實串接另由人工驗證。
