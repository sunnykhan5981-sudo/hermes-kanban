(() => {
  const API = {
    tasks: "/api/tasks",
    task: (id) => `/api/tasks/${id}`,
    assignees: "/api/assignees",
    stats: "/api/stats",
    boards: "/api/boards",
    moveTask: (id) => `/api/tasks/${id}/move`,
    completeTask: (id) => `/api/tasks/${id}/complete`,
    deleteTask: (id) => `/api/tasks/${id}/delete`,
  };

  const COLUMNS = [
    { key: "triage", label: "Ideas" },
    { key: "todo", label: "Research" },
    { key: "ready", label: "Planning" },
    { key: "running", label: "Dev" },
    { key: "blocked", label: "Testing" },
    { key: "done", label: "Done" },
  ];

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const board = $("#board");
  const searchBox = $("#searchBox");
  const assigneeFilter = $("#assigneeFilter");
  const priorityFilter = $("#priorityFilter");
  const createBtn = $("#createBtn");
  const refreshBtn = $("#refreshBtn");
  const statusText = $("#statusText");
  const statsText = $("#statsText");
  const createModal = $("#createModal");
  const drawer = $("#drawer");
  const drawerBackdrop = $("#drawerBackdrop");
  const dTitle = $("#dTitle");
  const dMeta = $("#dMeta");
  const dBody = $("#dBody");
  const toastEl = $("#toast");

  let allTasks = [];
  let draggableId = null;
  let currentDetailId = null;
  let selectedTaskIds = new Set();

  function updateBulkDeleteButton() {
    const bulkBtn = document.getElementById("bulkDeleteBtn");
    if (!bulkBtn) return;
    const count = selectedTaskIds.size;
    bulkBtn.style.display = count > 0 ? "inline-flex" : "none";
    bulkBtn.textContent = count > 0 ? `Delete Selected (${count})` : "Delete Selected";
  }

  function setStatus(msg) {
    if (statusText) statusText.textContent = msg;
  }

  function initials(name) {
    if (!name) return "?";
    return name.slice(0, 2).toUpperCase();
  }

  function colorFor(name) {
    const palette = [
      "#38bdf8",
      "#818cf8",
      "#f472b6",
      "#fb923c",
      "#4ade80",
      "#facc15",
      "#f87171",
    ];
    let hash = 0;
    for (const ch of String(name || "")) hash = (hash * 31 + ch.charCodeAt(0)) | 0;
    return palette[Math.abs(hash) % palette.length];
  }

  function statusClass(status) {
    const map = {
      done: "done",
      running: "running",
      ready: "ready",
      todo: "todo",
      triage: "triage",
      blocked: "blocked",
    };
    return map[status] || "todo";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function parseTasks(payload) {
    const items = [];
    const rows = (payload.tasks || []).filter(
      (task) => task && task.id
    );
    rows.forEach((task) => {
      const list = document.createElement("div");
      list.className = "card";
      list.draggable = true;
      list.dataset.id = task.id;
      list.innerHTML = `
        <div class="card-head">
          <span class="badge ${statusClass(task.status)}">${escapeHtml(task.id)}</span>
          <span class="assignee" style="background:${colorFor(task.assignee)}" title="${escapeHtml(task.assignee)}">${escapeHtml(initials(task.assignee))}</span>
        </div>
        <div class="card-body">${escapeHtml(task.title)}</div>
        <div class="card-foot">
          <span class="tag">${escapeHtml((task.priority || "medium"))}</span>
          <span class="tag">${escapeHtml(task.assignee || "unassigned")}</span>
        </div>
      `;
      list.addEventListener("click", (event) => {
        if (event.target.closest("button")) return;
        openTask(task.id);
      });
      list.addEventListener("dragstart", (event) => {
        draggableId = task.id;
        list.classList.add("dragging");
        event.dataTransfer.effectAllowed = "move";
      });
      list.addEventListener("dragend", () => {
        list.classList.remove("dragging");
        draggableId = null;
      });
      items.push(list);
    });
    return items;
  }

  async function api(method, path, body = null) {
    const opts = { method, headers: { "Content-Type": "application/json", Accept: "application/json" } };
    if (body !== null) opts.body = JSON.stringify(body);
    const res = await window.fetch(path, opts);
    const text = await res.text();
    let payload = {};
    try { payload = JSON.parse(text); } catch {}
    if (!res.ok) throw payload;
    return payload;
  }

  async function renderBoard() {
    if (!board) return;
    board.innerHTML = "";
    selectedTaskIds = new Set();
    updateBulkDeleteButton();
    COLUMNS.forEach((col) => {
      const isDoneColumn = col.key === "done" || col.key === "completed";
      const column = document.createElement("div");
      column.className = "column";
      column.dataset.status = col.key;
      column.innerHTML = `<div class="column-head"><div>${escapeHtml(col.label)}</div>${isDoneColumn ? '<label style="display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted);cursor:pointer"><input type="checkbox" id="selectAllDone" style="accent-color:#00f0ff"> Select all</label>' : ''}</div><div class="col-strip"></div>`;
      const list = document.createElement("div");
      list.className = "task-list";
      list.dataset.status = col.key;
      list.addEventListener("dragover", (event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
      });
      list.addEventListener("drop", (event) => {
        event.preventDefault();
        const target = event.target.closest(".task-list");
        const targetStatus = target ? target.dataset.status : null;
        if (draggableId && targetStatus) {
          moveTask(draggableId, targetStatus);
        }
      });
      column.appendChild(list);
      board.appendChild(column);
      if (isDoneColumn) {
        const selectAll = column.querySelector("#selectAllDone");
        if (selectAll) {
          selectAll.addEventListener("change", () => {
            const checked = selectAll.checked;
            const doneCards = list.querySelectorAll(".card");
            doneCards.forEach((card) => {
              const id = card.dataset.id;
              const box = card.querySelector(".done-select");
              if (!box || !id) return;
              box.checked = checked;
              if (checked) selectedTaskIds.add(id);
              else selectedTaskIds.delete(id);
            });
            updateBulkDeleteButton();
          });
        }
      }
    });

    api("GET", API.tasks)
      .then((payload) => {
        const loaded = Array.isArray(payload.tasks) ? payload.tasks : [];
        window.__kanbanTasks = loaded;
        const mapped = {};
        loaded.forEach((task) => {
          const status = String(
            !task || !task.status ? "triage" : task.status
          );
          mapped[status] = mapped[status] || [];
          mapped[status].push(task);
        });
        COLUMNS.forEach((col) => {
          const list = board.querySelector(`.task-list[data-status="${col.key}"]`);
          if (!list) return;
          list.innerHTML = "";
          (mapped[col.key] || []).forEach((task) => {
            const rawStatus = String(task.status || '').toLowerCase();
            const isCardDone = rawStatus === 'done' || rawStatus === 'completed' || rawStatus === 'complete';
            const card = document.createElement("div");
            card.className = "card ripple";
            card.draggable = true;
            card.dataset.id = task.id;
            card.dataset.priority = task.priority || "medium";
            card.innerHTML = `
              <div class="card-head">
                <span class="badge ${statusClass(task.status)}">${escapeHtml(task.id)}</span>
                <span class="assignee" style="background:${colorFor(task.assignee)}" title="${escapeHtml(task.assignee)}">${escapeHtml(initials(task.assignee))}</span>
              </div>
              <div class="card-body">${escapeHtml(task.title)}</div>
              <div class="card-foot">
                ${isCardDone ? `<label style="display:inline-flex;align-items:center;gap:6px;font-size:11px;color:var(--muted);cursor:pointer"><input class="done-select" type="checkbox" data-id="${escapeHtml(task.id)}" ${selectedTaskIds.has(task.id) ? 'checked' : ''}> Select</label>` : ''}
                <span class="tag">${escapeHtml(task.priority || "medium")}</span>
                <span class="tag">${escapeHtml(task.assignee || "unassigned")}</span>
              </div>
            `;
            const selectBox = card.querySelector(".done-select");
            if (selectBox) {
              selectBox.addEventListener("click", (event) => {
                event.stopPropagation();
                if (selectBox.checked) {
                  selectedTaskIds.add(task.id);
                } else {
                  selectedTaskIds.delete(task.id);
                }
                updateBulkDeleteButton();
              });
            }
            card.addEventListener("dragstart", (event) => {
              draggableId = task.id;
              card.classList.add("dragging");
              event.dataTransfer.effectAllowed = "move";
            });
            card.addEventListener("dragend", () => {
              card.classList.remove("dragging");
              draggableId = null;
            });
            card.addEventListener("click", (event) => {
              if (event.target.closest("button")) return;
              openTask(task.id);
            });
            list.appendChild(card);
          });
        });
        if (statusText) statusText.textContent = `Loaded ${loaded.length} tasks`;
      })
      .catch((err) => {
        console.error("[Kanban] Failed to load tasks", err);
        setStatus("Failed to load tasks");
      });
  }

  function safeToggle(selector, opened) {
    if (!selector) return;
    const el = typeof selector === "string" ? $(selector) : selector;
    if (!el) return;
    if (typeof opened === "boolean") {
      opened ? el.classList.add("open") : el.classList.remove("open");
    } else {
      el.classList.toggle("open");
    }
  }

  function openTask(id) {
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
  }

  function closeDrawer() {
    safeToggle(drawer, false);
    safeToggle(drawerBackdrop, false);
    currentDetailId = null;
  }

  async function moveTask(id, status) {
    setStatus("Moving task...");
    try { await api("POST", API.moveTask(id), { status }); } catch {}
    setStatus("Saved");
  }

  async function createTask() {
    const titleInput = $("#cTitle");
    const title = titleInput ? titleInput.value.trim() : "";
    if (!title) {
      toast("Title required");
      return;
    }
    setStatus("Creating task...");
    try {
      await api("POST", API.tasks, {
        title,
        assignee: $("#cAssignee") ? $("#cAssignee").value : "default",
        priority: $("#cPriority") ? $("#cPriority").value : "medium",
        description: $("#cDesc") ? $("#cDesc").value : "",
        pipelineMode: $("#cMode") ? $("#cMode").value : "feature",
      });
      if (createModal) createModal.classList.remove("open");
      if (titleInput) titleInput.value = "";
      const cDesc = $("#cDesc");
      if (cDesc) cDesc.value = "";
      toast("Task created");
    } catch (error) {
      console.error("[Kanban] Create failed", error);
      toast("Create failed");
      setStatus("Error");
    }
    setStatus("Saved");
  }

  function toast(message) {
    if (!toastEl) return;
    toastEl.textContent = message;
    toastEl.classList.add("show");
    setTimeout(() => toastEl.classList.remove("show"), 1800);
  }

  if (createBtn) {
    createBtn.addEventListener("click", () => {
      console.log("[Kanban] Create clicked");
      safeToggle(createModal, true);
    });
  }

  const cancelCreate = $("#cancelCreate");
  const submitCreate = $("#submitCreate");
  if (cancelCreate) cancelCreate.addEventListener("click", () => safeToggle(createModal, false));
  if (submitCreate) submitCreate.addEventListener("click", createTask);
  if (createModal) createModal.addEventListener("click", (event) => { if (event.target === createModal) safeToggle(createModal, false); });

  const dComplete = $("#dComplete");
  const dDelete = $("#dDelete");
  const dClose = $("#dClose");
  const bulkDeleteBtn = $("#bulkDeleteBtn");
  if (dClose) dClose.addEventListener("click", closeDrawer);
  if (drawerBackdrop) drawerBackdrop.addEventListener("click", closeDrawer);
  if (dComplete) {
    dComplete.addEventListener("click", () => {
      if (!currentDetailId) return;
      api("POST", `${API.task(currentDetailId)}/complete`, { summary: "Completed via dashboard" }).then(() => {
        toast("Task completed");
        closeDrawer();
        renderBoard();
      }).catch(() => toast("Complete failed"));
    });
  }
  if (dDelete) {
    dDelete.addEventListener("click", () => {
      if (!currentDetailId) return;
      const ok = confirm(`Archive ${currentDetailId}?`);
      if (!ok) return;
      api("POST", API.deleteTask(currentDetailId)).then(() => {
        toast("Task archived");
        closeDrawer();
        renderBoard();
      }).catch(() => toast("Delete failed"));
    });
  }

  if (bulkDeleteBtn) {
    bulkDeleteBtn.addEventListener("click", async () => {
      const ids = Array.from(selectedTaskIds);
      if (!ids.length) return;
      const ok = confirm(`Archive ${ids.length} selected task(s)?`);
      if (!ok) return;
      setStatus("Deleting selected...");
      try {
        await Promise.all(ids.map(id => api("POST", API.deleteTask(id))));
        selectedTaskIds = new Set();
        updateBulkDeleteButton();
        toast(`${ids.length} archived`);
        renderBoard();
        setStatus("Saved");
      } catch {
        toast("Bulk delete failed");
        setStatus("Error");
      }
    });
  }

  if (refreshBtn) refreshBtn.addEventListener("click", () => { console.log("[Kanban] Refresh clicked"); renderBoard(); });
  if (searchBox) searchBox.addEventListener("input", renderBoard);
  if (assigneeFilter) assigneeFilter.addEventListener("change", renderBoard);
  if (priorityFilter) priorityFilter.addEventListener("change", renderBoard);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDrawer();
      safeToggle(createModal, false);
    }
  });

  let touchStartX = 0;
  document.addEventListener("touchstart", (event) => {
    touchStartX = event.touches[0].clientX;
  }, { passive: true });
  document.addEventListener("touchend", (event) => {
    const dx = (event.changedTouches[0]?.clientX || 0) - touchStartX;
    if (Math.abs(dx) < 80) return;
    const statusOrder = ["triage", "todo", "ready", "running", "blocked", "done"];
    const drawerEl = document.getElementById("drawer");
    const fromColumn = document.elementFromPoint(event.changedTouches[0]?.clientX || 0, event.changedTouches[0]?.clientY || 0)?.closest(".task-list");
    const fromCard = document.elementFromPoint(event.changedTouches[0]?.clientX || 0, event.changedTouches[0]?.clientY || 0)?.closest(".card");
    const id = fromCard?.dataset?.id;
    if (!id || !fromColumn) return;
    const current = String(fromColumn.dataset.status || "triage");
    const idx = statusOrder.indexOf(current);
    const next = statusOrder[Math.max(0, Math.min(statusOrder.length - 1, idx + (dx < 0 ? 1 : -1)))];
    if (next && next !== current) moveTask(id, next);
  });

  renderBoard();
  const auroraCanvas = document.getElementById('auroraCanvas');
  if (auroraCanvas && window.requestAnimationFrame) {
    const ctx = auroraCanvas.getContext('2d');
    let w, h;
    function resize(){
      w = auroraCanvas.width = window.innerWidth;
      h = auroraCanvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);
    const particles = Array.from({length: 16}, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      r: 90 + Math.random() * 200,
      vx: (Math.random() - 0.5) * 0.28,
      vy: (Math.random() - 0.5) * 0.18,
      hue: 155 + Math.random() * 100,
      alpha: 0.05 + Math.random() * 0.10
    }));
    function draw(){
      ctx.clearRect(0,0,w,h);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < -p.r) p.x = w + p.r;
        if (p.x > w + p.r) p.x = -p.r;
        if (p.y < -p.r) p.y = h + p.r;
        if (p.y > h + p.r) p.y = -p.r;
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r);
        g.addColorStop(0, `hsla(${p.hue}, 55%, 55%, ${p.alpha})`);
        g.addColorStop(1, 'transparent');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      });
      requestAnimationFrame(draw);
    }
    draw();
  }
})();
