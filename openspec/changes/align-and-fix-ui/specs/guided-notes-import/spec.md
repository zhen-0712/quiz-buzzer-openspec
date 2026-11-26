# Spec Delta

## MODIFIED Requirements

### Requirement: Read the linked online Google Sheet
系統 MUST 接受 Google Sheet 連結並直接讀取線上結構，不得要求下載 xlsx 作為匯入來源。未指定工作表時，系統 MUST 依 Google Sheets 工作表順序略過沒有同一列「題號」與「作答」標題的工作表，並選取第一個同時具備兩標題的工作表。連結含 `gid` 時，系統 MUST 只讀取該工作表。選定工作表後解析失敗時 MUST 回報錯誤，不得改用後續工作表。

#### Scenario: Skip non-template worksheets and select the first matching worksheet
- **WHEN** Sheet 依序包含說明頁、第一個含完整標題列的工作表、以及另一個也含完整標題列的工作表
- **THEN** 系統略過說明頁，只解析第一個符合的工作表，並忽略後續候選工作表

#### Scenario: Read an accessible Google Sheet
- **WHEN** 老師提供可存取且至少一個工作表含完整標題列的 Google Sheet 連結
- **THEN** 系統依工作表順序選定第一個符合的工作表並開始解析

#### Scenario: Read only the worksheet specified by gid
- **WHEN** 老師提供含 `gid` 的 Sheet 連結
- **THEN** 系統只讀取及解析該 ID 的工作表，不掃描其他工作表作為替代

#### Scenario: Reject a gid that does not identify a worksheet
- **WHEN** 老師提供的 `gid` 不存在於該 Google Sheet
- **THEN** 系統拒絕匯入並顯示明確的工作表識別錯誤

#### Scenario: Do not scan other worksheets when the gid worksheet has no complete headers
- **WHEN** `gid` 指定的工作表沒有同一列完整「題號／作答」標題，而其他工作表有完整標題
- **THEN** 系統拒絕匯入並回報找不到可用標題，不掃描或改用其他工作表

#### Scenario: Do not fall back when the selected worksheet is invalid
- **WHEN** 第一個含完整標題列的工作表有無法唯一判讀的題號或填空，而後續工作表可解析
- **THEN** 系統指出第一個工作表及錯誤位置並拒絕匯入，不解析後續工作表

#### Scenario: Report when no worksheet has a complete header pair
- **WHEN** 所有工作表都沒有同一列的「題號」與「作答」標題
- **THEN** 系統拒絕匯入並回報找不到可用標題

#### Scenario: Sheet cannot be accessed
- **WHEN** 連結無效、權限不足或雲端讀取失敗
- **THEN** 系統中止匯入並顯示可理解的原因

### Requirement: Reject ambiguous question or answer mapping
系統 MUST 在選定工作表內題號或作答格無法唯一判讀時中止匯入，並指出工作表及位置。相同題號若在已結束的題號區塊後再次出現 MUST 視為非相鄰重複題號並拒絕；跨多列的同一題號合併範圍 MUST 視為同一區塊，不算重複。失敗匯入 MUST 不建立題目或變更既有活動的題目、來源及結構快照。

#### Scenario: Question number cannot be uniquely identified
- **WHEN** 缺少或重複的標題使題號欄無法唯一辨識，或資料列題號無法歸屬到唯一題目
- **THEN** 系統不建立該次匯入並指出工作表與位置

#### Scenario: Answer cells cannot be uniquely identified
- **WHEN** 選定工作表的作答標題欄或某題所屬填空格無法唯一辨識
- **THEN** 系統不建立該次匯入並指出工作表與位置

#### Scenario: Reject a repeated non-adjacent question number
- **WHEN** 題號 2 出現在題號 1 之後，並在後續另一個位置再次出現
- **THEN** 系統拒絕匯入並指出題號 2 首次及再次出現的工作表位置

#### Scenario: Do not treat a merged question number as a duplicate
- **WHEN** 同一題號的合併儲存格跨越多個作答列
- **THEN** 系統將其解析為一個題號區塊及多個依序排列的填空

#### Scenario: Reject multiple header rows in the selected worksheet
- **WHEN** 已選定工作表內出現多個完整「題號／作答」標題列
- **THEN** 系統指出工作表與多餘標題位置並拒絕匯入，不改選其他工作表

#### Scenario: Preserve the existing import when parsing fails
- **WHEN** 活動已有成功匯入的題目，而後續匯入因重複題號或結構歧義失敗
- **THEN** 系統保留原題目、來源 URL 與匯入時結構快照

#### Scenario: Import succeeds without a preconfigured question count
- **WHEN** 選定工作表中的所有題號與填空均可唯一判讀
- **THEN** 系統完成匯入，且題數等於解析出的題號區塊數
