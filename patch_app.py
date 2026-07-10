from pathlib import Path
p = Path('static/app.js')
s = p.read_text()
needle = '''  function openTask(id) {
    currentDetailId = id;
    const card = (window.__kanbanTasks || []).find(t => t.id === id);
    const title = card ? card.title : `Task ${id}`;
    const status = card ? card.status : "";
    const assignee = card ? card.assignee : "unassigned";
    const priority = card ? card.priority : "medium";
    const description = card ? card.description || "" : "";
    const rawStatus = String(status || "").toLowerCase();
    const isDone = ["done","completed","complete"].includes(rawStatus) || !!card?.completed;
    if (dTitle) dTitle.textContent = title;
    if (dMeta) dMeta.textContent = `${id} · ${escapeHtml(status || "")} · ${escapeHtml(assignee)}`;
    if (dBody) {
      let resultHtml = "";
      if (isDone || rawStatus === "blocked") {
        resultHtml += `<div><b>Execution Result</b><span id="dResult">Loading...</span></div>`;
      }
      dBody.innerHTML = `
        <div><b>Title</b><span>${escapeHtml(title)}</span></div>
        <div><b>Status</b><span>${escapeHtml(status)}</span></div>
        <div><b>Assignee</b><span>${escapeHtml(assignee)}</span></div>
        <div><b>Priority</b><span>${escapeHtml(priority)}</span></div>
        <div><b>Description</b><span>${escapeHtml(description)}</span></div>
        ${resultHtml}
      `;
      if (isDone || rawStatus === "blocked") {
        api("GET", `/api/tasks/${id}/runs`).then((rPayload) => {
          const resultEl = document.getElementById("dResult");
          if (!resultEl) return;
          const db = rPayload?.db || {};
          const latest = db.latest_run || {};
          const runStatus = latest.outcome || "";
          if (runStatus === "completed") {
            resultEl.textContent = latest.summary || "Completed via dashboard";
            return;
          }
          if (runStatus === "blocked") {
            resultEl.textContent = latest.summary || latest.error || "Blocked: needs input";
            return;
          }
          const summaries = Array.isArray(rPayload.summaries) ? rPayload.summaries : [];
          const runs = Array.isArray(rPayload.runs) ? rPayload.runs : [];
          const runsText = typeof rPayload.runs_text === "string" ? rPayload.runs_text.trim() : "";
          const completedLine = summaries.slice().reverse().find((x) => String(x || "").includes("Completed via dashboard"));
          const blockedLine = summaries.slice().reverse().find((x) => String(x || "").includes("Empty task body") || String(x || "").includes("Need clarification"));
          const latestLine = completedLine || blockedLine || summaries[0] || runsText || "No run history yet";
          resultEl.textContent = latestLine;
        }).catch(() => {
          const resultEl = document.getElementById("dResult");
          if (resultEl) resultEl.textContent = "Failed to load result";
        });
      }
    }
    safeToggle(drawer, true);
    safeToggle(drawerBackdrop, true);
  }'''
replacement = '''  function openTask(id) {
    currentDetailId = id;
    const card = (window.__kanbanTasks || []).find(t => t.id === id);
    const title = card ? card.title : `Task ${id}`;
    const status = card ? card.status : "";
    const assignee = card ? card.assignee : "unassigned";
    const priority = card ? card.priority : "medium";
    const description = card ? card.description || "" : "";
    const rawStatus = String(status || "").toLowerCase();
    const isDone = ["done","completed","complete"].includes(rawStatus) || !!card?.completed;
    if (isDone) {
      openDetails(id);
      return;
    }
    if (dTitle) dTitle.textContent = title;
    if (dMeta) dMeta.textContent = `${id} · ${escapeHtml(status || "")} · ${escapeHtml(assignee)}`;
    if (dBody) {
      dBody.innerHTML = `
        <div><b>Title</b><span>${escapeHtml(title)}</span></div>
        <div><b>Status</b><span>${escapeHtml(status)}</span></div>
        <div><b>Assignee</b><span>${escapeHtml(assignee)}</span></div>
        <div><b>Priority</b><span>${escapeHtml(priority)}</span></div>
        <div><b>Description</b><span>${escapeHtml(description)}</span></div>
      `;
    }
    safeToggle(drawer, true);
    safeToggle(drawerBackdrop, true);
  }

  function openDetails(id) {
    const card = (window.__kanbanTasks || []).find(t => t.id === id);
    const title = card ? card.title : `Task ${id}`;
    if (detTitle) detTitle.textContent = `Details · ${title}`;
    if (detBody) {
      const status = card ? card.status : "";
      const assignee = card ? card.assignee : "unassigned";
      const priority = card ? card.priority : "medium";
      const description = card ? card.description || "" : "";
      const rawStatus = String(status || "").toLowerCase();
      const isDone = ["done","completed","complete"].includes(rawStatus) || !!card?.completed;
      let resultBlock = "";
      if (isDone || rawStatus === "blocked") {
        resultBlock += `<div class="det-section"><b>Execution Result</b><span id="dResult">Loading...</span></div>`;
      }
      detBody.innerHTML = `
        <div class="det-section"><b>Title</b><span>${escapeHtml(title)}</span></div>
        <div class="det-section"><b>Status</b><span>${escapeHtml(status)}</span></div>
        <div class="det-section"><b>Assignee</b><span>${escapeHtml(assignee)}</span></div>
        <div class="det-section"><b>Priority</b><span>${escapeHtml(priority)}</span></div>
        <div class="det-section"><b>Description</b><span>${escapeHtml(description)}</span></div>
        ${resultBlock}
      `;
      if (isDone || rawStatus === "blocked") {
        api("GET", `/api/tasks/${id}/runs`).then((rPayload) => {
          const resultEl = document.getElementById("dResult");
          if (!resultEl) return;
          const db = rPayload?.db || {};
          const latest = db.latest_run || {};
          const runStatus = latest.outcome || "";
          if (runStatus === "completed") {
            resultEl.textContent = latest.summary || "Completed via dashboard";
            return;
          }
          if (runStatus === "blocked") {
            resultEl.textContent = latest.summary || latest.error || "Blocked: needs input";
            return;
          }
          const summaries = Array.isArray(rPayload.summaries) ? rPayload.summaries : [];
          const runs = Array.isArray(rPayload.runs) ? rPayload.runs : [];
          const runsText = typeof rPayload.runs_text === "string" ? rPayload.runs_text.trim() : "";
          const completedLine = summaries.slice().reverse().find((x) => String(x || "").includes("Completed via dashboard"));
          const blockedLine = summaries.slice().reverse().find((x) => String(x || "").includes("Empty task body") || String(x || "").includes("Need clarification"));
          const latestLine = completedLine || blockedLine || summaries[0] || runsText || "No run history yet";
          resultEl.textContent = latestLine;
        }).catch(() => {
          const resultEl = document.getElementById("dResult");
          if (resultEl) resultEl.textContent = "Failed to load result";
        });
      }
    }
    if (detailsPanel) detailsPanel.classList.add("open");
  }

  function closeDetails() {
    if (detailsPanel) detailsPanel.classList.remove("open");
    currentDetailId = null;
  }'''
if needle not in s:
  raise SystemExit('needle not found')
p.write_text(s.replace(needle, replacement))
print('ok')
