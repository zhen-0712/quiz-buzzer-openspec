# Proposal

## Why

需要將 Guided Notes 多工作表選擇統一為工作表順序，不受連結中的 `gid` 影響；匯出結構檢查也必須一次收集所有差異並確保零寫入。CSV 需防止 Excel 將答案解讀為公式，同時保持 Google Sheet 匯出內容不變。另需讓老師投影中的即時作答狀況預設收起，避免 DOM 呈現各組資料。

## What Changes

- 不論來源連結是否帶 `gid`，匯入都依工作表順序略過無標題頁，選第一個同列有「題號」及「作答」標題的工作表；選中後錯誤即停止，不採用後頁。匯出仍依匯入快照中的工作表 ID。
- 匯出前收集所有結構差異與填空數錯誤；任一問題都整份中止、零寫入，題目層級錯誤列出全部問題題號，工作表層級錯誤指出差異原因。
- CSV 改為「題號、組別、填空序號、答案、搶答順位」五欄，每填空一列；使用 UTF-8 BOM、CRLF 與 RFC 4180 escaping。答案以 `= + - @`、Tab、CR 或 LF 開頭時只在 CSV 答案欄前加單引號；Google Sheet 仍以原答案 `stringValue` 寫入。僅結束後老師可下載，只輸出有作答的勝出題。
- 明確要求結束後老師 API 不回傳被取代提交內容；資料庫保留歷史。現有實作已依 `is_effective` 篩選結束階段老師回應，加入回歸驗收鎖定此行為。
- 老師搶答中作答狀況預設收起；展開／收起控制只改前端呈現，收起時 DOM 不含提交資料，輪詢保留展開狀態，已結束時自動展開，重新整理後回預設收起。API 回應仍提供老師資料，README 說明此功能只保證投影畫面與 DOM。
- 更新 README 與 `docs/acceptance-matrix.md` 的對應說明與驗收方式。

## Capabilities

### Modified Capabilities

- `guided-notes-import`: 匯入不受 `gid` 影響，一律依工作表順序選第一個完整標題頁。
- `sheets-export`: 固定匯入工作表；全量檢查差異並零寫入中止；定義安全的 CSV 欄位、escaping 與公式前綴。
- `quiz-buzzer`: 結束後老師 API 僅回有效提交；新增老師即時作答狀況的收起／展開顯示規則。

## Impact

- 影響 Sheets adapter/parser/export、CSV 序列化、老師監看頁面、README 與驗收矩陣。
- 增補假 adapter 測試，涵蓋全部結構差異、零寫入及 CSV 安全格式；前端 DOM 收起行為以可行自動化測試或人工步驟驗證。
- 本 change 已依更新後的規劃完成實作與自動化驗收；人工驗證完成狀態記錄於 `tasks.md`。
