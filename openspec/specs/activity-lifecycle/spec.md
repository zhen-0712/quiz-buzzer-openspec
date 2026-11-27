# activity-lifecycle Specification

## Purpose
定義本機課堂活動的建立、老師控制、學生加入、階段推進與恢復行為，確保活動狀態和組別身分在同一活動中一致且可持續。

## Requirements

### Requirement: Teacher creates a protected activity
系統 MUST 讓老師建立活動並設定 1 至 100 組及活動密碼。密碼長度 MUST 為 6 至 64 字元、不得全為空白，且保存時 MUST 使用不可逆雜湊。

#### Scenario: Create activity with valid settings
- **WHEN** 老師輸入有效密碼並設定 1 至 100 組
- **THEN** 系統建立準備階段的活動、產生活動代碼並保存密碼雜湊

#### Scenario: Reject invalid password or group count
- **WHEN** 密碼過短、過長或全空白，或組數不在 1 至 100 範圍
- **THEN** 系統拒絕建立活動並指出無效欄位

### Requirement: Teacher authenticates to control an activity
系統 MUST 要求老師提供活動密碼，才能執行該活動的階段控制、全組監看或匯出操作。

#### Scenario: Teacher authenticates successfully
- **WHEN** 老師輸入該活動正確密碼
- **THEN** 系統授予該活動老師操作權限

#### Scenario: Teacher authentication fails
- **WHEN** 老師輸入錯誤密碼
- **THEN** 系統拒絕老師操作並回報驗證失敗

### Requirement: Students join or re-enter by activity and group
系統 MUST 允許學生在準備或搶答中以活動代碼及已設定範圍內的組別編號加入或重新進入；同一活動的同一組別編號 MUST 對應同一組且保留既有答案。已結束活動僅允許進入結果檢視。

#### Scenario: Join during preparation or active phase
- **WHEN** 學生在準備或搶答中輸入有效活動代碼及範圍內組別編號
- **THEN** 系統讓學生進入該組，不要求密碼

#### Scenario: Re-enter an existing group
- **WHEN** 學生以已存在的組別編號重新進入活動
- **THEN** 系統呈現同一組並保留該組原有作答

#### Scenario: Reject out-of-range group or invalid code
- **WHEN** 學生輸入不存在的活動代碼或超出活動組數的組別編號
- **THEN** 系統拒絕加入並顯示明確原因

#### Scenario: Enter an ended activity
- **WHEN** 學生以有效活動代碼及組別編號進入已結束活動
- **THEN** 系統只提供結果檢視，不提供加入搶答或提交作答的操作

### Requirement: Activity phases advance in order
活動階段 MUST 僅能由老師依「準備 → 搶答中 → 已結束」順序推進；階段不得倒退，已結束活動不得重新開啟。

#### Scenario: Advance to the next phase
- **WHEN** 老師要求進入下一階段
- **THEN** 系統將活動推進到緊接的下一階段

#### Scenario: Reject phase skipping or reopening
- **WHEN** 老師要求跳過階段、倒退階段或重新開啟已結束活動
- **THEN** 系統拒絕變更並保留目前階段

### Requirement: Require imported questions before starting the quiz
系統 MUST 至少成功匯入一題後，才允許老師將活動從準備切換到搶答中。

#### Scenario: Start after a successful question import
- **WHEN** 活動已有至少一題成功匯入且老師開始搶答
- **THEN** 系統允許活動進入搶答中

#### Scenario: Reject start without imported questions
- **WHEN** 活動沒有成功匯入任何題目且老師開始搶答
- **THEN** 系統拒絕階段變更並提示先匯入題目

### Requirement: Open screens synchronize phase changes
系統 MUST 以伺服器保存的階段為準，並讓仍連線的已開啟畫面在階段變更後 2 秒內更新，無須手動重整。

#### Scenario: Phase change appears in open screens
- **WHEN** 老師切換階段且學生與老師頁面仍連線
- **THEN** 所有已開啟畫面在 2 秒內顯示新階段

#### Scenario: Reconnect after temporary disconnection
- **WHEN** 頁面中斷連線後恢復連線
- **THEN** 頁面取得並顯示伺服器目前保存的階段

### Requirement: Persist activity state locally
系統 MUST 將活動、題目、提交與階段保存在本機，並於程序重新啟動後恢復資料及既有順位所需的序號狀態。

#### Scenario: Restore after restart
- **WHEN** 系統在有活動資料時重新啟動
- **THEN** 活動、題目、提交、階段及序號狀態均可恢復

#### Scenario: Continue submissions after restart
- **WHEN** 搶答中活動恢復後接受新提交
- **THEN** 新提交序號大於重啟前已接受的所有序號
