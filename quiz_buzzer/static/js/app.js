"use strict";

(() => {
  const labels = { preparation: "準備", active: "搶答中", ended: "已結束" };

  async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
      cache: "no-store",
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.message || "操作失敗，請稍後再試。 ");
    }
    return payload;
  }

  function showMessage(target, message, kind = "info") {
    if (!target) return;
    target.textContent = message || "";
    target.dataset.kind = kind;
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function addAnswers(parent, answers) {
    const list = element("ol", "answer-list");
    for (const answer of answers || []) list.append(element("li", "", answer));
    parent.append(list);
  }

  const home = document.querySelector("[data-create-form]");
  if (home) initializeHome();

  function initializeHome() {
    const message = document.querySelector("[data-home-message]");
    const createForm = document.querySelector("[data-create-form]");
    const loginForm = document.querySelector("[data-teacher-login-form]");
    const joinForm = document.querySelector("[data-join-form]");
    const codeInput = document.querySelector("#join-code");
    const groupInput = document.querySelector("#join-group");
    const groupRange = document.querySelector("[data-group-range]");

    createForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = createForm.querySelector("button[type=submit]");
      button.disabled = true;
      showMessage(message, "正在建立活動…");
      try {
        const form = new FormData(createForm);
        const activity = await apiRequest("/api/activities", {
          method: "POST",
          body: JSON.stringify({
            group_count: Number(form.get("group_count")),
            password: form.get("password"),
          }),
        });
        window.location.assign(`/activities/${encodeURIComponent(activity.activity_code)}/status`);
      } catch (error) {
        showMessage(message, error.message, "error");
      } finally {
        button.disabled = false;
      }
    });

    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = loginForm.querySelector("button[type=submit]");
      button.disabled = true;
      showMessage(message, "正在驗證老師密碼…");
      try {
        const form = new FormData(loginForm);
        const code = String(form.get("activity_code")).trim();
        await apiRequest(`/api/activities/${encodeURIComponent(code)}/teacher-login`, {
          method: "POST",
          body: JSON.stringify({ password: form.get("password") }),
        });
        window.location.assign(`/activities/${encodeURIComponent(code)}/status`);
      } catch (error) {
        showMessage(message, error.message, "error");
      } finally {
        button.disabled = false;
      }
    });

    async function updateGroupRange() {
      const code = codeInput.value.trim();
      if (!code) return;
      try {
        const info = await apiRequest(`/api/activities/${encodeURIComponent(code)}/status`);
        groupInput.min = "1";
        groupInput.max = String(info.group_count);
        groupRange.textContent = `此活動可選第 1 至 ${info.group_count} 組。`;
      } catch (error) {
        groupRange.textContent = error.message;
      }
    }
    codeInput.addEventListener("blur", updateGroupRange);
    codeInput.addEventListener("change", updateGroupRange);

    joinForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = joinForm.querySelector("button[type=submit]");
      button.disabled = true;
      showMessage(message, "正在加入活動…");
      try {
        const form = new FormData(joinForm);
        const code = String(form.get("activity_code")).trim();
        const requestedGroup = Number(form.get("group_number"));
        const info = await apiRequest(`/api/activities/${encodeURIComponent(code)}/status`);
        if (!Number.isInteger(requestedGroup) || requestedGroup < 1 || requestedGroup > info.group_count) {
          throw new Error(`組別編號須介於 1 至 ${info.group_count}。`);
        }
        await apiRequest(`/api/activities/${encodeURIComponent(code)}/join`, {
          method: "POST",
          body: JSON.stringify({ group_number: requestedGroup }),
        });
        window.location.assign(`/activities/${encodeURIComponent(code)}/status`);
      } catch (error) {
        showMessage(message, error.message, "error");
      } finally {
        button.disabled = false;
      }
    });
  }

  const activityView = document.querySelector("[data-activity-code]");
  if (activityView) initializeActivity();

  function initializeActivity() {
    const code = activityView.dataset.activityCode;
    const phaseLabel = document.querySelector("[data-phase-label]");
    const connection = document.querySelector("[data-connection-status]");
    const message = document.querySelector("[data-activity-message]");
    const guestView = document.querySelector("[data-guest-view]");
    const teacherView = document.querySelector("[data-teacher-view]");
    const studentView = document.querySelector("[data-student-view]");
    const importForm = document.querySelector("[data-import-form]");
    const importSummary = document.querySelector("[data-import-summary]");
    const teacherMonitor = document.querySelector("[data-teacher-monitor]");
    const phaseAction = document.querySelector("[data-phase-action]");
    const phaseHelp = document.querySelector("[data-phase-help]");
    const exportSection = document.querySelector("[data-export-section]");
    const exportButton = document.querySelector("[data-export-button]");
    const exportResult = document.querySelector("[data-export-result]");
    const downloadCsv = document.querySelector("[data-download-csv]");
    const studentWaiting = document.querySelector("[data-student-waiting]");
    const studentActive = document.querySelector("[data-student-active]");
    const studentQuestions = document.querySelector("[data-student-questions]");
    const studentResults = document.querySelector("[data-student-results]");
    const resultsList = document.querySelector("[data-results-list]");
    const studentGroup = document.querySelector("[data-student-group]");
    const resultGroup = document.querySelector("[data-result-group]");
    const importSection = document.querySelector("[data-import-section]");
    const submittingQuestions = new Set();
    const answerDrafts = new Map();
    const submissionFeedback = new Map();
    let monitorExpanded = false;
    let latestTeacherQuiz = null;
    let lastSignature = "";
    let lastRole = "";
    let polling = false;

    function setRole(role) {
      guestView.hidden = role !== "guest";
      teacherView.hidden = role !== "teacher";
      studentView.hidden = role !== "student";
    }

    function renderQuestions(questions) {
      importSummary.replaceChildren();
      if (!questions.length) {
        importSummary.append(element("p", "muted", "尚未匯入題目。"));
        return;
      }
      importSummary.append(element("p", "summary-line", `已匯入 ${questions.length} 題`));
      const list = element("ul", "compact-list");
      for (const question of questions) {
        list.append(element("li", "", `題號 ${question.question_number}｜${question.answer_count} 個填空`));
      }
      importSummary.append(list);
    }

    function renderTeacher(quiz) {
      const phase = quiz.phase;
      latestTeacherQuiz = quiz;
      if (phase === "ended") monitorExpanded = true;
      renderQuestions(quiz.questions || []);
      importSection.hidden = phase !== "preparation";
      exportSection.hidden = phase !== "ended";
      downloadCsv.href = `/api/activities/${encodeURIComponent(code)}/export.csv`;
      if (phase === "ended") {
        phaseAction.hidden = true;
        phaseHelp.textContent = "活動已結束，無法重新開啟。";
      } else {
        phaseAction.hidden = false;
        phaseAction.textContent = phase === "preparation" ? "開始搶答" : "結束活動";
        phaseAction.dataset.nextPhase = phase === "preparation" ? "active" : "ended";
        phaseAction.disabled = phase === "preparation" && !(quiz.questions || []).length;
        phaseHelp.textContent = phaseAction.disabled
          ? "開始搶答前請先成功匯入至少一題。"
          : phase === "preparation"
            ? "所有題目會同時開放。按下按鈕前會再次確認。"
            : "結束後學生可查看勝出結果，活動無法重新開啟。";
      }

      teacherMonitor.replaceChildren();
      if (phase === "preparation") return;
      teacherMonitor.append(element("h3", "", phase === "active" ? "即時監看" : "全部提交與順位"));
      if (phase === "active") {
        const toggle = element("button", "monitor-toggle", monitorExpanded ? "收起作答狀況" : "顯示作答狀況");
        toggle.type = "button";
        toggle.setAttribute("aria-expanded", String(monitorExpanded));
        toggle.addEventListener("click", () => {
          monitorExpanded = !monitorExpanded;
          renderTeacher(latestTeacherQuiz);
        });
        teacherMonitor.append(toggle);
        if (!monitorExpanded) return;
      }
      const rows = phase === "active" ? quiz.current_submissions || [] : quiz.submissions || [];
      if (!rows.length) {
        teacherMonitor.append(element("p", "muted", "目前尚無提交。"));
        return;
      }
      const tableWrap = element("div", "table-scroll");
      const table = element("table", "data-table");
      const head = element("thead");
      const headRow = element("tr");
      for (const label of ["題號", "組別", "答案", "順位"]) {
        headRow.append(element("th", "", label));
      }
      head.append(headRow);
      table.append(head);
      const body = element("tbody");
      for (const row of rows) {
        const tr = element("tr");
        tr.append(element("td", "", row.question_number));
        tr.append(element("td", "", `第 ${row.group_number} 組`));
        tr.append(element("td", "", (row.answers || []).join("、")));
        tr.append(element("td", "", row.rank ? String(row.rank) : "—"));
        body.append(tr);
      }
      table.append(body);
      tableWrap.append(table);
      teacherMonitor.append(tableWrap);
    }

    function renderStudent(quiz) {
      studentWaiting.hidden = quiz.phase !== "preparation";
      studentActive.hidden = quiz.phase !== "active";
      studentResults.hidden = quiz.phase !== "ended";
      studentGroup.textContent = String(quiz.group_number || "");
      resultGroup.textContent = String(quiz.group_number || "");

      if (quiz.phase === "active") {
        captureStudentDrafts();
        const saved = new Map((quiz.submissions || []).map((item) => [item.question_number, item]));
        studentQuestions.replaceChildren();
        for (const question of quiz.questions || []) {
          const card = element("article", "question-card");
          const heading = element("div", "question-heading");
          heading.append(element("h3", "", `題號 ${question.question_number}`));
          heading.append(element("span", "blank-count", `${question.answer_count} 格`));
          card.append(heading);
          const submitted = saved.get(question.question_number);
          if (submitted) {
            const status = element("div", "submitted-answer");
            status.append(element("strong", "status-badge", "已送出"));
            addAnswers(status, submitted.answers);
            card.append(status);
          }
          const form = element("form", "answer-form");
          form.dataset.questionNumber = question.question_number;
          for (let index = 0; index < question.answer_count; index += 1) {
            const field = element("label", "answer-field", `第 ${index + 1} 格答案`);
            const input = element("textarea", "");
            input.rows = 2;
            input.maxLength = 201;
            input.required = true;
            input.dataset.answerInput = "true";
            input.dataset.position = String(index + 1);
            input.setAttribute("aria-label", `題號 ${question.question_number} 第 ${index + 1} 格答案`);
            input.value = answerDrafts.get(question.question_number)?.[index] || "";
            field.append(input);
            form.append(field);
          }
          form.addEventListener("input", () => {
            answerDrafts.set(
              question.question_number,
              [...form.querySelectorAll("[data-answer-input]")].map((input) => input.value),
            );
            submissionFeedback.delete(question.question_number);
          });
          const submit = element("button", "", submitted ? "重新送出整題答案" : "送出整題答案");
          submit.type = "submit";
          submit.disabled = submittingQuestions.has(question.question_number);
          form.append(submit);
          const formMessage = element("p", "form-message");
          formMessage.dataset.formMessage = "true";
          formMessage.setAttribute("role", "status");
          form.append(formMessage);
          const feedback = submissionFeedback.get(question.question_number);
          if (feedback) showMessage(formMessage, feedback.message, feedback.kind);
          form.addEventListener("submit", (event) => submitAnswers(event, form, question));
          card.append(form);
          studentQuestions.append(card);
        }
      } else if (quiz.phase === "ended") {
        resultsList.replaceChildren();
        for (const result of quiz.results || []) {
          const card = element("article", "question-card result-card");
          card.append(element("h3", "", `題號 ${result.question_number}`));
          if (result.winner) {
            card.append(element("p", "winner-label", `搶答成功：第 ${result.winner.group_number} 組`));
            addAnswers(card, result.winner.answers);
          } else {
            card.append(element("p", "muted", "本題無人作答。"));
          }
          if (result.own) {
            card.append(element("p", "own-result-label", `本組答案 · 順位 ${result.own.rank}`));
            addAnswers(card, result.own.answers);
          } else {
            card.append(element("p", "muted", "本組未提交此題。"));
          }
          resultsList.append(card);
        }
      }
    }

    function captureStudentDrafts() {
      for (const form of studentQuestions.querySelectorAll("form[data-question-number]")) {
        answerDrafts.set(
          form.dataset.questionNumber,
          [...form.querySelectorAll("[data-answer-input]")].map((input) => input.value),
        );
      }
    }

    async function submitAnswers(event, form, question) {
      event.preventDefault();
      const questionNumber = question.question_number;
      if (submittingQuestions.has(questionNumber)) return;
      const inputs = [...form.querySelectorAll("[data-answer-input]")];
      const answers = inputs.map((input) => input.value.trim());
      const formMessage = form.querySelector("[data-form-message]");
      for (let index = 0; index < answers.length; index += 1) {
        if (!answers[index]) {
          showMessage(formMessage, `第 ${questionNumber} 題第 ${index + 1} 格不可空白。`, "error");
          inputs[index].focus();
          return;
        }
        if (answers[index].length > 200) {
          showMessage(formMessage, `第 ${questionNumber} 題第 ${index + 1} 格超過 200 字。`, "error");
          inputs[index].focus();
          return;
        }
      }
      submittingQuestions.add(questionNumber);
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      showMessage(formMessage, "正在送出…");
      let accepted = false;
      try {
        const result = await apiRequest(`/api/activities/${encodeURIComponent(code)}/submissions`, {
          method: "POST",
          body: JSON.stringify({ question_number: questionNumber, answers }),
        });
        accepted = true;
        answerDrafts.delete(questionNumber);
        submissionFeedback.set(questionNumber, {
          message: result.status || "已送出",
          kind: "success",
        });
      } catch (error) {
        submissionFeedback.set(questionNumber, { message: error.message, kind: "error" });
        if (/階段|搶答中/.test(error.message)) showMessage(message, "階段已變更，答案未送出；正在更新畫面。", "error");
      } finally {
        submittingQuestions.delete(questionNumber);
        const currentForm = [...studentQuestions.querySelectorAll("form[data-question-number]")]
          .find((candidate) => candidate.dataset.questionNumber === questionNumber);
        if (currentForm) {
          const currentButton = currentForm.querySelector("button[type=submit]");
          if (currentButton) currentButton.disabled = false;
          if (accepted) {
            for (const input of currentForm.querySelectorAll("[data-answer-input]")) {
              input.value = "";
            }
          }
          const currentMessage = currentForm.querySelector("[data-form-message]");
          const feedback = submissionFeedback.get(questionNumber);
          if (feedback) showMessage(currentMessage, feedback.message, feedback.kind);
        }
        await poll();
      }
    }

    importForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = document.querySelector("[data-import-button]");
      const url = new FormData(importForm).get("sheet_url");
      button.disabled = true;
      showMessage(message, "正在解析 Guided Notes…");
      try {
        const result = await apiRequest(`/api/activities/${encodeURIComponent(code)}/import`, {
          method: "POST",
          body: JSON.stringify({ sheet_url: url }),
        });
        const summary = element("p", "success-line", `匯入成功：${result.question_count} 題`);
        const list = element("ul", "compact-list");
        for (const question of result.questions || []) {
          list.append(element("li", "", `題號 ${question.question_number}｜${question.answer_count} 個填空`));
        }
        importSummary.replaceChildren(summary, list);
        showMessage(message, "題目已匯入。", "success");
        await poll();
      } catch (error) {
        showMessage(message, error.message, "error");
      } finally {
        button.disabled = false;
      }
    });

    phaseAction.addEventListener("click", async () => {
      if (phaseAction.disabled || phaseAction.hidden) return;
      const nextPhase = phaseAction.dataset.nextPhase;
      const prompt = nextPhase === "active"
        ? "開始搶答後所有題目會同時開放。確定開始嗎？"
        : "結束後學生只能檢視結果，且活動無法重開。確定結束嗎？";
      if (!window.confirm(prompt)) return;
      phaseAction.disabled = true;
      try {
        await apiRequest(`/api/activities/${encodeURIComponent(code)}/phase`, {
          method: "POST",
          body: JSON.stringify({ phase: nextPhase }),
        });
        showMessage(message, `活動已切換至「${labels[nextPhase]}」。`, "success");
        await poll();
      } catch (error) {
        showMessage(message, error.message, "error");
        await poll();
      }
    });

    exportButton.addEventListener("click", async () => {
      if (exportButton.disabled || activityView.dataset.phase !== "ended") return;
      const confirmed = window.confirm(
        "請先備份原 Google Sheet。確認已完成備份，並要以目前勝出答案覆寫作答格嗎？"
      );
      if (!confirmed) return;
      exportButton.disabled = true;
      showMessage(exportResult, "正在重新檢查 Sheet 結構並匯出…");
      try {
        const result = await apiRequest(`/api/activities/${encodeURIComponent(code)}/export`, {
          method: "POST",
          body: JSON.stringify({ confirm_backup: true }),
        });
        showMessage(
          exportResult,
          `匯出成功：寫入 ${result.questions_written} 題、${result.cells_written} 格。`,
          "success",
        );
      } catch (error) {
        showMessage(exportResult, `匯出失敗：${error.message}`, "error");
      } finally {
        exportButton.disabled = false;
      }
    });

    async function poll() {
      if (polling) return;
      polling = true;
      try {
        const status = await apiRequest(`/api/activities/${encodeURIComponent(code)}/status`);
        activityView.dataset.phase = status.phase;
        activityView.dataset.phaseVersion = String(status.phase_version);
        phaseLabel.textContent = labels[status.phase] || status.phase;
        connection.textContent = "已連線 · 每秒同步";
        connection.dataset.state = "online";
        setRole(status.role);
        if (status.role !== lastRole) {
          lastRole = status.role;
          lastSignature = "";
        }
        if (status.role === "guest") {
          lastSignature = "guest";
          return;
        }
        const quiz = await apiRequest(`/api/activities/${encodeURIComponent(code)}/quiz`);
        const signature = JSON.stringify({ status, quiz });
        if (signature === lastSignature) return;
        lastSignature = signature;
        if (status.role === "teacher") renderTeacher(quiz);
        else renderStudent(quiz);
      } catch (_error) {
        connection.textContent = "連線中斷，正在重新連線";
        connection.dataset.state = "offline";
      } finally {
        polling = false;
      }
    }

    poll();
    const timer = window.setInterval(poll, 1000);
    window.addEventListener("pagehide", () => window.clearInterval(timer), { once: true });
    window.addEventListener("pageshow", () => poll());
  }
})();
