"use strict";

(() => {
  const activityView = document.querySelector("[data-activity-code]");
  if (!activityView) return;

  const labels = {
    preparation: "準備",
    active: "搶答中",
    ended: "已結束",
  };
  const phaseLabel = document.querySelector("[data-phase-label]");
  const connectionStatus = document.querySelector("[data-connection-status]");
  const activityCode = activityView.dataset.activityCode;

  async function refreshActivityStatus() {
    try {
      const response = await fetch(
        `/api/activities/${encodeURIComponent(activityCode)}/status`,
        { cache: "no-store" },
      );
      if (!response.ok) throw new Error("活動狀態讀取失敗");
      const status = await response.json();
      activityView.dataset.phase = status.phase;
      activityView.dataset.phaseVersion = String(status.phase_version);
      phaseLabel.textContent = labels[status.phase] || status.phase;
      activityView.dataset.connectionState = "online";
      connectionStatus.textContent = "已連線";
      document.dispatchEvent(new CustomEvent("activitystatus", { detail: status }));
    } catch (_error) {
      activityView.dataset.connectionState = "offline";
      connectionStatus.textContent = "連線中斷，正在重新連線";
    }
  }

  refreshActivityStatus();
  const timer = window.setInterval(refreshActivityStatus, 1000);
  window.addEventListener("pagehide", () => window.clearInterval(timer), { once: true });
})();
