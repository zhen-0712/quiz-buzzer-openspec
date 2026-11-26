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
已結束後，學生 MUST 能檢視每題搶答成功組別及其答案，並能辨識自己組的答案與順位；其他未成功組別的答案 MUST 不公開。老師結束畫面的全部提交表格 MUST 對每題每組只呈現最新有效答案及其順位，不呈現已被重送取代的舊答案；資料庫 MUST 保留完整提交歷史。

#### Scenario: Student views a question winner after the end
- **WHEN** 學生檢視已結束活動的結果
- **THEN** 系統呈現每題成功組別與其答案，並標示該學生組別的答案與順位

#### Scenario: Hide non-winning answers from students
- **WHEN** 已結束活動的某題有未成功組的提交
- **THEN** 學生無法檢視該未成功組的答案

#### Scenario: Teacher views all submissions after the end
- **WHEN** 老師檢視已結束活動的全部提交表格
- **THEN** 每題每組只顯示最新有效提交及其順位，不顯示被重送取代的舊提交

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
