# Spec Delta

## MODIFIED Requirements

### Requirement: Re-read and compare the source structure before export
每次匯出前，系統 MUST 重新讀取並解析匯入時選定的原始工作表；若來源試算表、工作表識別碼、題號、作答格數、順序或位置與匯入時記錄的結構不一致，MUST 中止匯出並說明差異。當匯入連結未指定 `gid` 時，匯出仍 MUST 以匯入時保存的工作表 ID 為準，不得因工作表順序或其他分頁的標題而改選工作表。

#### Scenario: Export proceeds when the structure is unchanged
- **WHEN** 系統重新讀取匯入時指定的工作表，且來源及題目／作答格結構一致
- **THEN** 系統進入答案寫回流程

#### Scenario: Stop when the structure changed
- **WHEN** 匯入時記錄的工作表中題號、作答格數、順序或位置改變，或結構無法唯一解析
- **THEN** 系統中止匯出、不寫入任何答案，並指出造成中止的原因或位置

#### Scenario: Stop when the imported worksheet is unavailable
- **WHEN** 匯出前無法讀取匯入時記錄的工作表或該工作表 ID 與匯入快照不一致
- **THEN** 系統中止匯出、不宣告成功並顯示讀取或識別錯誤

#### Scenario: Ignore later matching worksheets during export
- **WHEN** 未指定 `gid` 的匯入已選定第一個符合標題規則的工作表，而後續工作表新增或修改成也符合標題規則
- **THEN** 匯出仍只重新解析匯入時保存的工作表，不改選其他分頁

#### Scenario: Do not use another worksheet when the imported worksheet changes
- **WHEN** 匯入時選定的工作表結構已改變，但另一工作表仍可解析
- **THEN** 系統中止匯出且零寫入，不以另一工作表替代

#### Scenario: Stop when the source cannot be read
- **WHEN** 匯出前無法存取原始 Google Sheet
- **THEN** 系統中止匯出、不宣告成功並顯示讀取錯誤
