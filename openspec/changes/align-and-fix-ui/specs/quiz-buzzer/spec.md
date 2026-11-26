# Spec Delta

## MODIFIED Requirements

### Requirement: Replace a group's complete answer on resubmission
搶答中，同組同題的有效答案 MUST 為最後一次被接受的整題提交；任何通過驗證的重送 MUST 整筆取代舊答案並取得新的伺服器序號，即使答案內容與前一次完全相同。驗證失敗的重送 MUST 保留原有效答案及序號。

#### Scenario: Accepted resubmission replaces the old answer
- **WHEN** 同組對同一題送出另一筆有效整題答案
- **THEN** 系統以新答案完整取代舊答案並保留新提交的序號

#### Scenario: Rejected resubmission preserves the old answer
- **WHEN** 同組重送的答案未通過整題驗證
- **THEN** 系統拒絕重送並保留原有效答案及其序號

#### Scenario: Accept identical content as a new resubmission
- **WHEN** 同組再次送出與目前有效答案完全相同且通過驗證的整題答案
- **THEN** 系統仍建立新提交並配發更大的伺服器序號，順位依新序號重新計算

### Requirement: Reveal winning results to students after the activity ends
已結束後，學生 MUST 能檢視每題搶答成功組別及其答案，並能辨識自己組的答案與順位；其他未成功組別的答案 MUST 不公開。老師結束畫面及老師查詢 API MUST 對每題每組只回傳／呈現最新有效答案及其順位，不回傳被重送取代的舊提交內容；資料庫 MUST 保留完整提交歷史。

#### Scenario: Student views a question winner after the end
- **WHEN** 學生檢視已結束活動的結果
- **THEN** 系統呈現每題成功組別與其答案，並標示該學生組別的答案與順位

#### Scenario: Hide non-winning answers from students
- **WHEN** 已結束活動的某題有未成功組的提交
- **THEN** 學生無法檢視該未成功組的答案

#### Scenario: Teacher views all submissions after the end
- **WHEN** 老師檢視已結束活動的全部提交表格
- **THEN** 每題每組只顯示最新有效提交及其順位，不顯示被重送取代的舊提交

#### Scenario: Teacher API omits replaced submissions after the end
- **WHEN** 老師在已結束階段查詢 quiz API，且同一組同一題有多次被接受的提交
- **THEN** 回應只包含每組每題最新有效答案及順位，不包含任何被取代提交的答案內容

#### Scenario: Preserve old submissions in history
- **WHEN** 同組同題已有多次被接受的提交且活動結束
- **THEN** 老師畫面只呈現最新有效提交，但資料庫仍保存該組該題的所有提交紀錄

## ADDED Requirements

### Requirement: Keep student submission controls usable after a request
學生提交按鈕 MUST 僅在該題提交請求處理期間停用。請求成功或失敗後，當前畫面中該題的提交按鈕 MUST 恢復可用，且重新啟用不得依賴已被輪詢重畫取代的舊表單節點。

#### Scenario: Re-enable submission after success
- **WHEN** 學生送出整題答案且伺服器接受
- **THEN** 畫面更新提交狀態後仍可再次送出該題

#### Scenario: Re-enable submission after failure
- **WHEN** 學生送出整題答案但伺服器拒絕或請求失敗
- **THEN** 顯示錯誤且該題提交按鈕恢復可用

### Requirement: Preserve unsent student answer drafts during polling
搶答中輪詢重畫題目區前，系統 MUST 保存每題尚未送出的答案草稿，並在重畫後依題號及填空順序還原。成功送出的題目 MAY 清空草稿；失敗提交的題目及其他未送出的題目 MUST 保留草稿。

#### Scenario: Keep drafts for other questions while polling
- **WHEN** 學生在多題輸入草稿，且輪詢更新題目區
- **THEN** 所有未送出的題目仍顯示原有草稿

#### Scenario: Clear the successfully submitted question only
- **WHEN** 學生成功送出其中一題而題目區重新繪製
- **THEN** 該題草稿可清空，其他題的未送草稿保留

#### Scenario: Preserve a draft after a rejected submission
- **WHEN** 學生提交某題失敗且題目區重新繪製
- **THEN** 該題及其他題的未送答案草稿均保留

### Requirement: Collapse the teacher's live answer monitor by default
老師頁面僅在搶答中提供即時作答狀況的顯示／收起控制，初始畫面 MUST 預設收起。收起時 DOM MUST 不渲染任何組別作答資料，包括各題作答組數、提交清單、組別、答案、名次或順位，不得僅以 CSS 隱藏資料。老師可按「顯示作答狀況」展開，再次操作可收起；輪詢重畫 MUST 保留目前展開狀態。重新載入頁面後 MUST 回到預設收起，不保存展開狀態。活動進入已結束階段時 MUST 自動展開結果，不需老師操作。此控制只改前端顯示，老師 API 仍回傳監看資料，資料及順位計算不變。

#### Scenario: Collapse live submissions on initial active view
- **WHEN** 老師首次在搶答中開啟或重新載入活動頁
- **THEN** 作答狀況預設收起，DOM 不包含各組作答數、提交、組別、答案或順位

#### Scenario: Expand and collapse the live monitor by control
- **WHEN** 老師在搶答中操作作答狀況控制
- **THEN** 「顯示作答狀況」會展開並渲染資料，再次操作可收起且移除作答資料 DOM

#### Scenario: Preserve the expanded state during polling
- **WHEN** 老師已展開作答狀況且輪詢取得更新
- **THEN** 監看狀況仍保持展開並顯示最新資料

#### Scenario: Reset the live monitor after page reload
- **WHEN** 老師重新載入搶答中活動頁
- **THEN** 作答狀況回到預設收起，未持久化先前展開狀態

#### Scenario: Automatically expand the results after the activity ends
- **WHEN** 活動階段變更為已結束
- **THEN** 老師頁面自動展開結果，不需再按顯示控制

#### Scenario: Keep the teacher API unchanged while collapsing the page
- **WHEN** 老師頁面收起即時作答狀況
- **THEN** 老師 API 仍回傳原有監看資料，前端只是不將其渲染到 DOM
