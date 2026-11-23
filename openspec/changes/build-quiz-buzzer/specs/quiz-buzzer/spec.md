# Spec Delta

## Purpose

定義學生提交整題答案及系統判定順位的規則，並規範老師在搶答中的監看資訊與學生於各階段可檢視的作答和結果。

## ADDED Requirements

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
搶答中，同組同題的有效答案 MUST 為最後一次被接受的整題提交；接受重送時 MUST 整筆取代該組該題的舊答案。

#### Scenario: Accepted resubmission replaces the old answer
- **WHEN** 同組對同一題送出另一筆有效整題答案
- **THEN** 系統以新答案完整取代舊答案並保留新提交的序號

#### Scenario: Rejected resubmission preserves the old answer
- **WHEN** 同組重送的答案未通過整題驗證
- **THEN** 系統拒絕重送並保留原有效答案及其序號

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
準備與搶答中，學生 MUST 僅能檢視自己組別的作答及狀態，且不得取得其他組的答案、作答狀況或順位。

#### Scenario: Student views own answer during the active phase
- **WHEN** 學生在搶答中檢視活動
- **THEN** 系統僅呈現該學生組別的作答及狀態

#### Scenario: Student cannot inspect other groups before the end
- **WHEN** 學生在準備或搶答中查詢活動結果
- **THEN** 系統不提供其他組的答案、作答狀況或順位

### Requirement: Let the teacher monitor submissions and current ranks live
搶答中，老師 MUST 能即時檢視各組已作答的題目及各題目前順位；順位 MUST 反映目前各組最後一次被接受的提交。

#### Scenario: Teacher monitors current submissions
- **WHEN** 老師在搶答中查看監看畫面
- **THEN** 系統列出各組已作答題目及各題目前順位

#### Scenario: Teacher sees rank update after resubmission
- **WHEN** 任一組的重送被接受
- **THEN** 老師畫面更新該題目前順位及該組最新答案

### Requirement: Reveal winning results to students after the activity ends
已結束後，學生 MUST 能檢視每題搶答成功組別及其答案，並能辨識自己組的答案與順位；其他未成功組別的答案 MUST 不公開。老師 MUST 能檢視全部提交與順位。

#### Scenario: Student views a question winner after the end
- **WHEN** 學生檢視已結束活動的結果
- **THEN** 系統呈現每題成功組別與其答案，並標示該學生組別的答案與順位

#### Scenario: Hide non-winning answers from students
- **WHEN** 已結束活動的某題有未成功組的提交
- **THEN** 學生無法檢視該未成功組的答案

#### Scenario: Teacher views all submissions after the end
- **WHEN** 老師檢視已結束活動
- **THEN** 系統呈現所有組別提交與各題順位
