#!/usr/bin/env python3
"""
Hermes Kanban Dashboard - Backend API (Way 2: SQLite-backed, hermes-independent)
"""
import json
import math
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# CSP header to allow inline scripts/styles (fixes iPhone Safari button clicks)
@app.after_request
def add_csp_headers(response):
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "img-src 'self' data: https:; "
        "font-src 'self' https: data:; "
        "connect-src 'self' https: wss:; "
        "frame-ancestors 'self';"
    )
    return response

STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')

# Board/path config: always reuse the existing local Hermes board data
KANBAN_BOARD = r"C:\Users\PROJECT-1\AppData\Local\hermes\kanban"
DB_PATH = r"C:\Users\PROJECT-1\AppData\Local\hermes\kanban.db"
DEFAULT_DB_PATH = DB_PATH

# Auto-init DB tables on import — required for Render / gunicorn,
# because `if __name__ == '__main__'` does NOT run when deployed.
try:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    _auto_init_con = sqlite3.connect(DB_PATH)
    _auto_init_con.row_factory = sqlite3.Row
    _auto_init_cur = _auto_init_con.cursor()
    _auto_init_cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT DEFAULT '',
            assignee TEXT DEFAULT 'default',
            status TEXT DEFAULT 'ready',
            priority INTEGER DEFAULT 0,
            created_by TEXT DEFAULT 'user',
            created_at INTEGER,
            started_at INTEGER,
            completed_at INTEGER,
            workspace_kind TEXT DEFAULT 'scratch',
            workspace_path TEXT,
            branch_name TEXT,
            tenant TEXT,
            result TEXT,
            consecutive_failures INTEGER DEFAULT 0,
            last_failure_error TEXT,
            block_kind TEXT,
            block_recurrences INTEGER DEFAULT 0,
            current_step_key TEXT,
            updated_at INTEGER
        )
        """
    )
    _auto_init_cur.execute(
        """
        CREATE TABLE IF NOT EXISTS task_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            profile TEXT DEFAULT 'default',
            step_key TEXT,
            status TEXT DEFAULT 'ready',
            started_at INTEGER,
            ended_at INTEGER,
            outcome TEXT,
            summary TEXT,
            error TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        )
        """
    )
    _auto_init_cur.execute(
        """
        CREATE TABLE IF NOT EXISTS task_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            author TEXT DEFAULT 'system',
            body TEXT DEFAULT '',
            created_at INTEGER DEFAULT (strftime('%s','now'))
        )
        """
    )
    _auto_init_cur.execute(
        """
        CREATE TABLE IF NOT EXISTS task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            kind TEXT DEFAULT 'generic',
            payload TEXT DEFAULT '{}',
            created_at INTEGER DEFAULT (strftime('%s','now'))
        )
        """
    )
    _auto_init_con.commit()
    _auto_init_con.close()
except Exception as _e:
    print(f"[DB_INIT] init failed: {_e}")

# Background dispatcher control
dispatcher_thread = None
dispatcher_running = False
dispatcher_interval = int(os.environ.get("DISPATCHER_INTERVAL", "30"))  # seconds

# Column mapping: UI name -> DB status
COLUMN_TO_STATUS = {
    "ideas": "triage",
    "research": "todo",
    "planning": "ready",
    "dev": "running",
    "testing": "blocked",
    "marketing": "running",
    "ready": "ready",
    "done": "done",
}
STATUS_TO_COLUMN = {v: k for k, v in COLUMN_TO_STATUS.items()}


def _db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _now_ts():
    return int(datetime.now(timezone.utc).timestamp())


def _row_to_task(r):
    return {
        "id": r["id"],
        "title": r["title"],
        "body": r["body"],
        "assignee": r["assignee"],
        "status": r["status"],
        "priority": r["priority"] if r["priority"] is not None else 0,
        "created_by": r["created_by"],
        "created_at": r["created_at"],
        "started_at": r["started_at"],
        "completed_at": r["completed_at"],
        "workspace_kind": r["workspace_kind"],
        "workspace_path": r["workspace_path"],
        "branch_name": r["branch_name"],
        "tenant": r["tenant"],
        "result": r["result"],
        "description": r["body"] or "",
        "consecutive_failures": r["consecutive_failures"] or 0,
        "last_failure_error": r["last_failure_error"],
        "block_kind": r["block_kind"],
        "block_recurrences": r["block_recurrences"] or 0,
        "current_step_key": r["current_step_key"],
    }


def _is_done(task: dict) -> bool:
    status = (task.get("status") or "").lower()
    return status in {"done", "completed", "archive"} or bool(task.get("completed_at"))


def tasks_to_board_payload(rows):
    board = {
        "triage": [],
        "todo": [],
        "ready": [],
        "running": [],
        "blocked": [],
        "archived": [],
        "done": [],
    }
    for row in rows:
        task = _row_to_task(row)
        status = (task["status"] or "ready").lower()
        board.setdefault(status, [])
        board[status].append(task)
    return board


def get_latest_run(con, task_id):
    cur = con.cursor()
    cur.execute(
        """
        SELECT id, profile, step_key, status, started_at, ended_at, outcome, summary, error
        FROM task_runs
        WHERE task_id = ?
        ORDER BY started_at DESC
        LIMIT 10
        """,
        (task_id,),
    )
    rows = cur.fetchall()
    runs = []
    for r in rows:
        runs.append({
            "id": r[0],
            "profile": r[1],
            "step_key": r[2],
            "status": r[3],
            "started_at": r[4],
            "ended_at": r[5],
            "outcome": r[6],
            "summary": r[7],
            "error": r[8],
        })
    return runs


def get_comments(con, task_id, limit=10):
    cur = con.cursor()
    cur.execute(
        """
        SELECT author, body, created_at
        FROM task_comments
        WHERE task_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (task_id, limit),
    )
    rows = cur.fetchall()
    out = []
    for r in rows:
        out.append({
            "author": r[0],
            "body": r[1],
            "created_at": r[2],
        })
    return out


def get_events(con, task_id, limit=20):
    cur = con.cursor()
    cur.execute(
        """
        SELECT kind, payload, created_at
        FROM task_events
        WHERE task_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (task_id, limit),
    )
    rows = cur.fetchall()
    out = []
    for r in rows:
        out.append({
            "kind": r[0],
            "payload": r[1],
            "created_at": r[2],
        })
    return out


# PWA manifest
PWA_MANIFEST = {
    "name": "Hermes Kanban",
    "short_name": "Hermes",
    "description": "Multi-Agent Kanban Dashboard for Hermes AI",
    "start_url": "/",
    "display": "standalone",
    "orientation": "portrait-primary",
    "background_color": "#000000",
    "theme_color": "#000000",
    "scope": "/",
    "icons": [
        {
            "src": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect fill='%231a1a2e' width='100' height='100' rx='22'/%3E%3Ctext x='50%25' y='55%25' dominant-baseline='middle' text-anchor='middle' font-size='50'%3E%F0%9F%93%8B%3C/text%3E%3C/svg%3E",
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any maskable",
        }
    ],
    "categories": ["productivity", "business"],
}


@app.route('/')
def index():
    return send_from_directory(STATIC_FOLDER, 'index.html')


@app.route('/manifest.json')
def manifest_json():
    return jsonify(PWA_MANIFEST)


@app.route('/api/boards')
def get_boards():
    return jsonify({"boards": [{"slug": "default", "name": "Default"}]})


@app.route('/health')
def health():
    ok = os.path.exists(DB_PATH)
    return jsonify({
        "status": "ok" if ok else "db_missing",
        "service": "hermes-kanban-dashboard",
        "db": DB_PATH,
        "db_exists": ok,
    })


@app.route('/api/tasks')
def get_tasks():
    try:
        con = _db()
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, title, body, assignee, status, priority,
                   created_by, created_at, started_at, completed_at,
                   workspace_kind, workspace_path, branch_name, tenant,
                   result, consecutive_failures, last_failure_error,
                   block_kind, block_recurrences, current_step_key
            FROM tasks
            ORDER BY created_at DESC
            """
        )
        rows = cur.fetchall()
        # Frontend (app.js renderBoard) expects a flat `tasks` array.
        return jsonify({"tasks": [_row_to_task(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/board')
def get_board():
    try:
        con = _db()
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, title, body, assignee, status, priority,
                   created_by, created_at, started_at, completed_at,
                   workspace_kind, workspace_path, branch_name, tenant,
                   result, consecutive_failures, last_failure_error,
                   block_kind, block_recurrences, current_step_key
            FROM tasks
            ORDER BY created_at DESC
            """
        )
        rows = cur.fetchall()
        return jsonify(tasks_to_board_payload(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tasks/<task_id>')
def get_task(task_id):
    try:
        con = _db()
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, title, body, assignee, status, priority,
                   created_by, created_at, started_at, completed_at,
                   workspace_kind, workspace_path, branch_name, tenant,
                   result, consecutive_failures, last_failure_error,
                   block_kind, block_recurrences, current_step_key
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"detail": _row_to_task(row)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tasks/<task_id>/runs')
def get_task_runs(task_id):
    try:
        con = _db()
        runs = get_latest_run(con, task_id)
        latest = runs[0] if runs else {}
        return jsonify({
            "runs": runs,
            "db": {
                "latest_run": latest,
                "comments": get_comments(con, task_id),
                "events": get_events(con, task_id),
            },
        })
    except Exception as e:
        return jsonify({"error": str(e), "runs": []}), 500


@app.route('/api/tasks/<task_id>/complete', methods=['POST'])
def complete_task(task_id):
    try:
        payload = request.get_json() or {}
        summary = payload.get("summary", "Completed via dashboard")
        ts = _now_ts()
        con = _db()
        cur = con.cursor()
        cur.execute(
            """
            UPDATE tasks
            SET status = 'done', completed_at = ?, result = ?
            WHERE id = ?
            """,
            (ts, summary, task_id),
        )
        con.commit()
        cur.execute(
            """
            INSERT INTO task_runs (task_id, profile, status, started_at, ended_at, outcome, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, "dashboard", "completed", ts - 1, ts, "completed", summary),
        )
        con.commit()
        return jsonify({"success": True, "output": summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tasks/<task_id>/move', methods=['POST'])
def move_task(task_id):
    data = request.get_json() or {}
    new_status = data.get("status", "")
    hermes_status = COLUMN_TO_STATUS.get(new_status, new_status)
    try:
        ts = _now_ts()
        con = _db()
        cur = con.cursor()
        cur.execute(
            """
            UPDATE tasks
            SET status = ?, started_at = ?
            WHERE id = ?
            """,
            (hermes_status, ts, task_id),
        )
        con.commit()
        return jsonify({"success": True, "new_status": new_status})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tasks/<task_id>/delete', methods=['POST'])
def delete_task(task_id):
    try:
        con = _db()
        cur = con.cursor()
        cur.execute("UPDATE tasks SET status = 'archived' WHERE id = ?", (task_id,))
        con.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.get_json() or {}
    title = data.get("title", "")
    assignee = data.get("assignee", "default")
    priority = data.get("priority", "medium")
    description = data.get("description", "")
    pipeline_mode = data.get("pipelineMode", "feature")
    if not title:
        return jsonify({"error": "Title required"}), 400
    task_id = "t_" + __import__("random", fromlist=["random"]).randbytes(6).hex()
    ts = _now_ts()
    try:
        con = _db()
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO tasks
            (id, title, body, assignee, status, priority, created_by, created_at, workspace_kind, workspace_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                title,
                description,
                assignee,
                "ready",
                1 if priority == "high" else 0,
                "user",
                ts,
                "scratch",
                os.path.join(KANBAN_BOARD, "workspaces", task_id),
            ),
        )
        con.commit()
        return jsonify({"success": True, "id": task_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/stats')
def get_stats():
    try:
        con = _db()
        cur = con.cursor()
        cur.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
        rows = cur.fetchall()
        per_status = {r[0]: r[1] for r in rows}
        cur.execute("SELECT assignee, COUNT(*) FROM tasks GROUP BY assignee")
        rows = cur.fetchall()
        per_assignee = {r[0]: r[1] for r in rows}
        return jsonify({
            "per_status": per_status,
            "per_assignee": per_assignee,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/assignees')
def get_assignees():
    try:
        con = _db()
        cur = con.cursor()
        cur.execute("SELECT DISTINCT assignee FROM tasks WHERE assignee IS NOT NULL")
        rows = cur.fetchall()
        return jsonify({"assignees": [r[0] for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/sw.js')
def service_worker():
    return jsonify({}), 200, {'Content-Type': 'application/javascript'}


if __name__ == '__main__':
    os.makedirs(STATIC_FOLDER, exist_ok=True)
    port = int(os.environ.get("PORT", 9121))
    print(f"Starting Kanban Dashboard on http://0.0.0.0:{port}")
    print(f"DB: {DB_PATH}")
    print("Press Ctrl+C to stop")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
