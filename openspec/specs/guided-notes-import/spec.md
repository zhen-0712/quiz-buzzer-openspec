# guided-notes-import Specification

## Purpose
定義從老師提供的線上 Guided Notes Google Sheet 讀取題號及作答格的行為，讓題目與答案位置依表格結構解析，而非依賴固定儲存格位置。

## Requirements

### Requirement: Import questions only during preparation
系統 MUST 僅允許在準備階段匯入題目；準備階段可重複匯入，成功匯入時以新解析的題目整批取代先前匯入的題目。搶答中與已結束階段 MUST 拒絕匯入。

#### Scenario: Import questions during preparation
- **WHEN** 老師在準備階段匯入可唯一解析的 Sheet
- **THEN** 系統匯入解析出的題目

#### Scenario: Re-import and replace the previous questions
- **WHEN** 老師在準備階段再次成功匯入另一份或已更新的 Sheet
- **THEN** 系統以此次解析的題目與來源結構取代先前匯入資料

#### Scenario: Reject import while the quiz is active
- **WHEN** 老師在搶答中要求匯入題目
- **THEN** 系統拒絕匯入且不變更既有題目

#### Scenario: Reject import after the activity ends
- **WHEN** 老師在已結束階段要求匯入題目
- **THEN** 系統拒絕匯入且不變更既有題目

### Requirement: Read the linked online Google Sheet
系統 MUST 接受 Google Sheet 連結並直接讀取線上結構，不得要求下載 xlsx 作為匯入來源。無論連結是否帶 `gid`，系統 MUST 依 Google Sheets 工作表順序略過沒有同一列「題號」與「作答」標題的工作表，並選取第一個同時具備兩標題的工作表。選定工作表後解析失敗時 MUST 回報錯誤，不得改用後續工作表；後續工作表即使也符合標題條件也 MUST 忽略。

#### Scenario: Skip non-template worksheets and select the first matching worksheet
- **WHEN** Sheet 依序包含無標題說明頁、第一個含完整標題列的工作表、以及另一個也含完整標題列的工作表
- **THEN** 系統略過說明頁，只解析第一個符合的工作表，並忽略後續候選工作表

#### Scenario: Read an accessible Google Sheet
- **WHEN** 老師提供可存取且至少一個工作表含完整標題列的連結，不論網址是否帶 `gid`
- **THEN** 系統都依工作表順序選定第一個符合的工作表並開始解析

#### Scenario: Do not fall back when the selected worksheet is invalid
- **WHEN** 第一個含完整標題列的工作表有無法唯一判讀的題號或填空，而後續工作表可解析
- **THEN** 系統指出第一個工作表及錯誤位置並拒絕匯入，不解析後續工作表

#### Scenario: Report when no worksheet has a complete header pair
- **WHEN** 所有工作表都沒有同一列的「題號」與「作答」標題
- **THEN** 系統拒絕匯入並回報找不到可用標題

#### Scenario: Sheet cannot be accessed
- **WHEN** 連結無效、權限不足或雲端讀取失敗
- **THEN** 系統中止匯入並顯示可理解的原因

### Requirement: Discover question and answer cells dynamically
系統 MUST 依工作表標題列中的「題號」及「作答」欄定位題目與填空，不得依賴寫死的列號或欄號，且 MUST 支援合併儲存格。

#### Scenario: Headers appear at a non-fixed location
- **WHEN** 有效標題列位於非固定列或欄位置
- **THEN** 系統依標題定位題號與作答欄並解析其下方資料

#### Scenario: Question number is merged across rows
- **WHEN** 一個題號儲存格合併涵蓋多個作答資料列
- **THEN** 系統將該合併範圍內依序出現的作答格歸屬於該題號

### Requirement: Support single questions and question groups
系統 MUST 將每個唯一題號解析為一題；只需題號與作答格，不要求題目敘述。該題可有一個或多個作答格，且同一工作表 MUST 可混合單填空題與多填空題。

#### Scenario: Import mixed question types
- **WHEN** Sheet 同時包含各自一個填空的題號與各自多個填空的題號
- **THEN** 系統依解析出的作答格數建立單題與題組，並以表格順序排列填空

#### Scenario: Determine question count from the Sheet
- **WHEN** Sheet 結構可唯一解析出題目
- **THEN** 系統以解析結果建立全部題目，不要求老師另外設定預期題數

#### Scenario: Import does not require question descriptions
- **WHEN** Sheet 具有可解析的題號與作答格但沒有題目敘述
- **THEN** 系統仍可完成匯入

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
