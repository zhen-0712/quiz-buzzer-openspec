# Spec Delta

## Purpose

定義活動結束後將搶答成功答案寫回原始線上 Google Sheet 的行為，並在寫入前確認來源表格結構仍與匯入時相符。

## ADDED Requirements

### Requirement: Export is available only after the activity ends
系統 MUST 僅允許老師在活動已結束後執行 Sheet 匯出，並 MUST 在匯出前提醒老師備份原始 Sheet。

#### Scenario: Teacher starts an export after the end
- **WHEN** 老師在已結束活動選擇匯出
- **THEN** 系統先提示備份原始 Sheet，再進行匯出

#### Scenario: Reject export before the end
- **WHEN** 老師在準備或搶答中要求匯出
- **THEN** 系統拒絕匯出且不寫入 Sheet

### Requirement: Re-read and compare the source structure before export
每次匯出前，系統 MUST 重新讀取並解析原始 Sheet；若來源、題號、作答格數、順序或位置與匯入時記錄的結構不一致，MUST 中止匯出並說明差異。

#### Scenario: Export proceeds when the structure is unchanged
- **WHEN** 重新解析結果與匯入時記錄的來源及題目／作答格結構一致
- **THEN** 系統進入答案寫回流程

#### Scenario: Stop when the structure changed
- **WHEN** 重新解析發現來源或題號、作答格數、順序或位置改變，或結構無法唯一解析
- **THEN** 系統中止匯出、不寫入任何答案，並指出造成中止的原因或位置

#### Scenario: Stop when the source cannot be read
- **WHEN** 匯出前無法存取原始 Sheet
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
