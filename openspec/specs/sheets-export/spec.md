# sheets-export Specification

## Purpose
定義活動結束後將搶答成功答案寫回原始線上 Google Sheet 的行為，並在寫入前確認來源表格結構仍與匯入時相符。

## Requirements

### Requirement: Export is available only after the activity ends
系統 MUST 僅允許老師在活動已結束後執行 Sheet 匯出，並 MUST 在匯出前提醒老師備份原始 Sheet。

#### Scenario: Teacher starts an export after the end
- **WHEN** 老師在已結束活動選擇匯出
- **THEN** 系統先提示備份原始 Sheet，再進行匯出

#### Scenario: Reject export before the end
- **WHEN** 老師在準備或搶答中要求匯出
- **THEN** 系統拒絕匯出且不寫入 Sheet

### Requirement: Re-read and compare the source structure before export
每次匯出前，系統 MUST 重新讀取並解析匯入時保存的工作表 ID 所指向的工作表，不受來源 URL 的 `gid` 影響；若來源試算表、工作表識別碼、工作表名稱、標題列／欄位置、題號、作答格數、順序或位置與匯入快照不同，MUST 中止整次匯出並零寫入。系統 MUST 收集全部題目層級差異，錯誤訊息列出所有有問題的題號與原因；來源、工作表 ID／名稱、標題列等工作表層級差異 MUST 指出差異欄位及原因。任何差異發生時不得只報第一個差異後就略過其餘題目，也不得部分寫入。

#### Scenario: Export proceeds when the structure is unchanged
- **WHEN** 系統重新讀取匯入時指定的工作表，且來源及所有題目／作答格結構一致
- **THEN** 系統完成全部預檢後才進入答案寫回流程

#### Scenario: Stop when the structure changed
- **WHEN** 匯入時記錄的來源或工作表層級結構有差異
- **THEN** 系統中止匯出、不寫入任何答案，並指出所有可辨識的差異原因

#### Scenario: List every question with a question-level difference
- **WHEN** 重新解析發現多題的題號、順序、填空數、填空順序或座標與快照不同
- **THEN** 系統中止匯出且零寫入，錯誤訊息列出全部有問題的題號及各題差異

#### Scenario: Abort all writes when stored blank counts do not match
- **WHEN** 任何題目的本機填空格數與保存快照或重新解析結果不一致
- **THEN** 系統中止整次匯出且零寫入，列出所有填空數不一致的題號

#### Scenario: Stop when the imported worksheet is unavailable
- **WHEN** 匯出前無法讀取匯入時記錄的工作表或工作表 ID 不存在
- **THEN** 系統中止匯出、不宣告成功並顯示讀取或工作表識別原因

#### Scenario: Ignore later matching worksheets during export
- **WHEN** 匯入時已依工作表順序選定一個工作表，而後續工作表新增或修改成也符合標題規則
- **THEN** 匯出仍只重新解析匯入時保存的工作表 ID，不改選其他分頁

#### Scenario: Stop when the source cannot be read
- **WHEN** 匯出前無法存取原始 Google Sheet
- **THEN** 系統中止匯出、不宣告成功並顯示讀取錯誤

### Requirement: Write winning answers to their original answer cells as plain text
系統 MUST 將每題搶答成功組的答案按填空順序寫回匯入時對應的原始作答格，並以純文字寫入；無人作答的題目 MUST 保持原樣。

#### Scenario: Write a single-blank winning answer
- **WHEN** 一題有搶答成功組且結構比對通過
- **THEN** 系統將成功組答案以純文字寫入該題原作答格

#### Scenario: Write a multi-blank winning answer
- **WHEN** 題組有搶答成功組且結構比對通過
- **THEN** 系統依序將第 i 個答案以純文字寫入第 i 個原作答格

#### Scenario: Preserve cells for unanswered questions
- **WHEN** 某題沒有任何已接受提交
- **THEN** 系統不修改該題任何原始作答格

#### Scenario: Report write failure
- **WHEN** 寫回部分或全部答案時雲端 API 回報失敗
- **THEN** 系統明確回報匯出失敗且不得顯示匯出成功

### Requirement: Isolate Google Sheets access behind a replaceable interface
系統 MUST 透過可替換的存取介面讀取 Sheet 結構與寫入答案；自動化測試 MUST 使用假實作，不得連線至真實 Google 服務。

#### Scenario: Automated export test uses a fake adapter
- **WHEN** 執行 Sheet 匯出自動化測試
- **THEN** 測試使用假存取實作驗證讀取、比對及寫入呼叫，且不連線至 Google

#### Scenario: Real adapter uses the Google Sheets API
- **WHEN** 使用者在本機設定有效 Google 憑證並執行真實串接
- **THEN** 系統透過 Google 官方 API 套件讀取結構及寫入答案

### Requirement: Download a winner-only CSV after the activity ends
系統 MUST 僅允許已結束活動的老師下載結果 CSV。CSV MUST 使用 UTF-8 BOM、CRLF 換行及 RFC 4180 相容的逗號與雙引號 escaping；欄位依序 MUST 為「題號、組別、填空序號、答案、搶答順位」。每個勝出題的每個填空 MUST 各佔一列，填空序號從 1 起算，同題各列組別與順位相同；無人作答的題 MUST 不列出。答案若以 `=`, `+`, `-`, `@`, Tab、CR 或 LF 開頭，系統 MUST 只在 CSV 答案欄字串前加單引號；不得在其他欄位加前綴，亦不得改變寫入 Google Sheet 的答案內容。

#### Scenario: Download the CSV only for a teacher after the end
- **WHEN** 已驗證老師在已結束階段下載 CSV
- **THEN** 系統回傳結果 CSV；學生、未驗證使用者或未結束活動的下載要求均被拒絕

#### Scenario: Write the five CSV columns and one row per blank
- **WHEN** 勝出題包含一個或多個填空答案
- **THEN** CSV 以指定五欄輸出，每個填空一列、序號從 1 開始，同題各列沿用相同組別及順位

#### Scenario: Omit questions without a submission
- **WHEN** 某題沒有任何已接受提交
- **THEN** CSV 不輸出該題的答案列

#### Scenario: Prefix spreadsheet-formula-like answer values only in CSV
- **WHEN** 答案分別以 `=`, `+`, `-`, `@`, Tab、CR 或 LF 開頭
- **THEN** CSV 答案欄在原字串前加單引號，其他欄位不加前綴，Google Sheet 寫入仍使用未加前綴的原答案字串

#### Scenario: Escape commas and double quotes using RFC 4180
- **WHEN** 答案含逗號或雙引號
- **THEN** CSV 正確以雙引號括欄並將內含雙引號重複跳脫，仍可解析回原答案

#### Scenario: Include BOM and CRLF record separators
- **WHEN** 老師下載 CSV
- **THEN** 位元組以 UTF-8 BOM 開頭，所有記錄以 CRLF 分隔

#### Scenario: Match the required safety serialization example
- **WHEN** 勝出答案依序為 `=SUM(1,2)`、`+1`、`-1`、`@a` 及 `含逗號,和"雙引號"`
- **THEN** CSV 答案欄依序序列化為 `"'=SUM(1,2)"`、`'+1`、`'-1`、`'@a` 及 `"含逗號,和""雙引號"""`，每列格式與順位符合欄位順序

#### Scenario: Emit the expected BOM, header, rows, and CRLF output
- **WHEN** 五個單填空勝出題的答案依序為上述安全序列化範例
- **THEN** UTF-8 BOM 後的 CSV 內容為 `題號,組別,填空序號,答案,搶答順位\r\n1,1,1,"'=SUM(1,2)",1\r\n2,1,1,'+1,1\r\n3,1,1,'-1,1\r\n4,1,1,'@a,1\r\n5,1,1,"含逗號,和""雙引號""",1\r\n`

#### Scenario: Keep one rank across all blanks in a question group
- **WHEN** 勝出題是有兩個填空的題組
- **THEN** CSV 輸出填空序號 1 與 2 兩列，兩列的題號、組別及搶答順位相同
