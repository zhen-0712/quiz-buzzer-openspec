# quiz-buzzer Specification

## Purpose
定義學生提交整題答案及系統判定順位的規則，並規範老師在搶答中的監看資訊與學生於各階段可檢視的作答和結果。

## Requirements

### Requirement: Open all questions simultaneously
活動進入搶答中時，系統 MUST 同時開放全部匯入題目，學生可自行選擇作答題目。

#### Scenario: All questions become available together
- **WHEN** 老師將活動從準備切換到搶答中
- **THEN** 學生可立即對任一題提交答案，不需等待前一題完成

### Requirement: Show the active question list to students
搶答中，學生 MUST 能看到全部題號及各題填空格數；系統不要求或顯示題目敘述。準備階段學生 MUST 看不到題目清單。

#### Scenario: Student sees question numbers and blank counts during the quiz
- **WHEN** 學生在搶答中檢視題目清單
- **THEN** 系統顯示全部題號及各題填空格數，不顯示題目敘述

#### Scenario: Student does not see questions during preparation
- **WHEN** 學生在準備階段檢視活動
- **THEN** 系統不顯示題目清單或題目資訊

### Requirement: Accept complete question submissions only during the active phase
系統 MUST 僅在搶答中接受整題提交；每次提交的答案數 MUST 等於該題填空數，每個答案去除前後空白後不得為空，且每個答案不得超過 200 字。驗證失敗時 MUST 拒絕整筆提交。

#### Scenario: Accept a complete question submission
- **WHEN** 一組在搶答中送出答案數量正確、非空且各不超過 200 字的整題答案
- **THEN** 系統接受並保存該組該題的答案

#### Scenario: Reject too few or too many answers
- **WHEN** 提交答案數少於或多於該題填空數
- **THEN** 系統拒絕整筆提交且不保存部分答案

#### Scenario: Reject blank or overlength answers
- **WHEN** 任一答案去除前後空白後為空或超過 200 字
- **THEN** 系統拒絕整筆提交並指出無效答案

#### Scenario: Reject submission outside the active phase
- **WHEN** 學生在準備或已結束階段提交答案
- **THEN** 系統拒絕提交且不修改既有答案

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

### Requirement: Rank groups by the latest accepted server sequence
每筆被接受的提交 MUST 取得伺服器遞增序號，不使用客戶端時間；每組每題以最後一次被接受的序號作為有效序號，各題由有效序號小到大決定順位。系統 MUST 不以答案正確性判定順位。

#### Scenario: Rank by effective submission sequence
- **WHEN** 多組在同一題各有一筆或多筆已接受提交
- **THEN** 系統使用各組最後一筆被接受提交的伺服器序號，由小到大排列該題順位

#### Scenario: Resubmission changes effective rank
- **WHEN** 一組重送答案且該重送在其他組提交後才被接受
- **THEN** 系統以重送序號重新計算順位，該組順位可因此後移

#### Scenario: Ignore correctness and client clock
- **WHEN** 答案內容看似正確但較晚提交，或裝置時間早於其他組
- **THEN** 系統仍只依伺服器接受序號判定順位

### Requirement: Treat a question group as one ranked submission
多填空題 MUST 以一筆整題提交及單一有效序號參與順位判定，並以該組對應填空順序保存答案。

#### Scenario: Rank a multi-blank question once
- **WHEN** 一組提交一題組中的所有填空答案
- **THEN** 該組在該題組只有一個有效序號與一個順位

### Requirement: Limit live student visibility before the activity ends
準備與搶答中，學生 MUST 僅能檢視自己組別的資料。搶答中，學生 MUST 只看到自己組每題目前有效答案與「已送出」狀態；學生的任何 API 回應 MUST NOT 包含順位、序號、提交時間、有效提交標記或其他可推斷順位的欄位。順位 MUST 僅在活動結束後的結果檢視提供。學生 MUST NOT 取得其他組的答案、作答狀況或順位。

#### Scenario: Student views own answer during the active phase
- **WHEN** 學生在搶答中檢視活動
- **THEN** 系統僅呈現該學生組別每題目前有效答案及「已送出」狀態，且不包含順位、序號、提交時間或有效提交標記

#### Scenario: Student submission acknowledgement hides ordering data
- **WHEN** 學生在搶答中成功提交或重送答案
- **THEN** 提交 API 僅回傳題號、已接受答案及「已送出」狀態，不回傳順位、序號、提交時間或可推斷順位的欄位

#### Scenario: Student cannot inspect other groups before the end
- **WHEN** 學生在準備或搶答中查詢活動結果
- **THEN** 系統不提供其他組的答案、作答狀況、順位、序號或提交時間

#### Scenario: Student receives own rank only after the activity ends
- **WHEN** 學生在已結束階段檢視結果
- **THEN** 系統提供每題勝出組別及答案，並提供該學生組別答案與順位，不提供提交序號

### Requirement: Let the teacher monitor submissions and current ranks live
搶答中，老師 MUST 能即時檢視各組已作答的題目及各題目前順位；順位 MUST 反映目前各組最後一次被接受的提交。

#### Scenario: Teacher monitors current submissions
- **WHEN** 老師在搶答中查看監看畫面
- **THEN** 系統列出各組已作答題目及各題目前順位

#### Scenario: Teacher sees rank update after resubmission
- **WHEN** 任一組的重送被接受
- **THEN** 老師畫面更新該題目前順位及該組最新答案

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
