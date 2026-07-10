from pathlib import Path

p = Path('static/app.js')
s = p.read_text()

# 1) inject details vars after drawerBackdrop
old1 = '  const drawerBackdrop = $(\"#drawerBackdrop\");\n  const dTitle = $(\"#dTitle\");'
new1 = '  const drawerBackdrop = $(\"#drawerBackdrop\");\n  const detailsPanel = $(\"#detailsPanel\");\n  const detTitle = $(\"#detTitle\");\n  const detBody = $(\"#detBody\");\n  const detClose = $(\"#detClose\");\n  const dTitle = $(\"#dTitle\");'
assert old1 in s, 'old1 missing'
s = s.replace(old1, new1)

# 2) replace openTask body
old_open = '''  function openTask(id) {
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
new_open = '''  function openTask(id) {
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
assert old_open in s, 'old_open missing'
s = s.replace(old_open, new_open)

# 3) after closeDrawer ensure details closes + detClose listener
old_close = '''  function closeDrawer() {
    safeToggle(drawer, false);
    safeToggle(drawerBackdrop, false);
    currentDetailId = null;
  }'''
new_close = '''  function closeDrawer() {
    safeToggle(drawer, false);
    safeToggle(drawerBackdrop, false);
    currentDetailId = null;
    if (detailsPanel) detailsPanel.classList.remove("open");
  }'''
assert old_close in s, 'old_close missing'
s = s.replace(old_close, new_close)

anchor = '  if (dClose) dClose.addEventListener("click", closeDrawer);\n'
replacement = anchor + '  if (detClose) detClose.addEventListener("click", closeDetails);\n  if (detailsPanel) detailsPanel.addEventListener("click", (e) => { if (e.target === detailsPanel) closeDetails(); });\n'
assert anchor in s, 'anchor missing'
s = s.replace(anchor, replacement)

# 4) Escape should close both
old_esc = '      closeDrawer();\n      safeToggle(createModal, false);'
new_esc = '      closeDrawer();\n      closeDetails();\n      safeToggle(createModal, false);'
assert old_esc in s, 'old_esc missing'
s = s.replace(old_esc, new_esc)

# 5) route create button + FAB both to modal
old_create = '''  if (createBtn) {
    createBtn.addEventListener("click", () => {
      console.log("[Kanban] Create clicked");
      safeToggle(createModal, true);
    });
  }'''
new_create = '''  function openCreateModal(){ if (createModal) createModal.classList.add("open"); }
  function closeCreateModal(){ if (createModal) createModal.classList.remove("open"); }
  if (createBtn) createBtn.addEventListener("click", openCreateModal);
  const fabBtn = $(\"#fab\");
  if (fabBtn) fabBtn.addEventListener(\"click\", openCreateModal);'''
assert old_create in s, 'old_create missing'
s = s.replace(old_create, new_create)

# 6) wire cancel/submit to new helpers
old_cancel = '  const cancelCreate = $(\"#cancelCreate\");\n  const submitCreate = $(\"#submitCreate\");\n  if (cancelCreate) cancelCreate.addEventListener(\"click\", () => safeToggle(createModal, false));\n  if (submitCreate) submitCreate.addEventListener(\"click\", createTask);'
new_cancel = '  const cancelCreate = $(\"#cancelCreate\");\n  const submitCreate = $(\"#submitCreate\");\n  if (cancelCreate) cancelCreate.addEventListener(\"click\", closeCreateModal);\n  if (submitCreate) submitCreate.addEventListener(\"click\", createTask);'
assert old_cancel in s, 'old_cancel missing'
s = s.replace(old_cancel, new_cancel)

# 7) modal backdrop click also close via helper
old_back = '  if (createModal) createModal.addEventListener("click", (event) => { if (event.target === createModal) safeToggle(createModal, false); });'
new_back = '  if (createModal) createModal.addEventListener("click", (event) => { if (event.target === createModal) closeCreateModal(); });'
assert old_back in s, 'old_back missing'
s = s.replace(old_back, new_back)

p.write_text(s)
print('patched app.js')
