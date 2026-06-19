#!/usr/bin/env python3
"""
Hermes Kanban Dashboard - Backend API
Runs locally, wraps `hermes kanban` CLI commands as REST API
"""
import subprocess
import json
import os
import threading
import time
from flask import Flask, jsonify, request, send_from_directory, send_file
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
HERMES_CMD = "hermes"

# Kanban board path for Render persistent disk
KANBAN_BOARD = os.environ.get("HERMES_KANBAN_BOARD", "/data/hermes-kanban")

# Background dispatcher control
dispatcher_thread = None
dispatcher_running = False
dispatcher_interval = int(os.environ.get("DISPATCHER_INTERVAL", "30"))  # seconds

def run_hermes(args):
    try:
        # Use the mounted disk for kanban database on Render
        # Set environment variables for hermes CLI
        env = os.environ.copy()
        env["HERMES_KANBAN_BOARD"] = os.environ.get("HERMES_KANBAN_BOARD", "/data/hermes-kanban")
        env["XDG_CONFIG_HOME"] = "/data/hermes"
        env["XDG_DATA_HOME"] = "/data/hermes"
        
        cmd = ["hermes"] + args
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timeout", 1
    except Exception as e:
        return "", str(e), 1

def run_kanban_dispatch():
    """Run a single kanban dispatch cycle"""
    try:
        stdout, stderr, code = run_hermes(['kanban', 'dispatch'])
        if code != 0 and stderr:
            print(f"Dispatcher warning: {stderr}")
        return code == 0
    except Exception as e:
        print(f"Dispatcher error: {e}")
        return False

def dispatcher_loop():
    """Background loop that runs kanban dispatch periodically"""
    global dispatcher_running
    print(f"[Dispatcher] Starting background dispatcher (interval: {dispatcher_interval}s)")
    dispatcher_running = True
    
    while dispatcher_running:
        try:
            print("[Dispatcher] Running kanban dispatch...")
            run_kanban_dispatch()
        except Exception as e:
            print(f"[Dispatcher] Error: {e}")
        
        # Sleep with early exit check
        for _ in range(dispatcher_interval):
            if not dispatcher_running:
                break
            time.sleep(1)
    
    print("[Dispatcher] Stopped")

def start_dispatcher():
    global dispatcher_thread, dispatcher_running
    if dispatcher_thread is not None and dispatcher_thread.is_alive():
        print("[Dispatcher] Already running")
        return
    
    dispatcher_running = True
    dispatcher_thread = threading.Thread(target=dispatcher_loop, daemon=True)
    dispatcher_thread.start()
    print("[Dispatcher] Background dispatcher started")

def stop_dispatcher():
    global dispatcher_running, dispatcher_thread
    dispatcher_running = False
    if dispatcher_thread is not None:
        dispatcher_thread.join(timeout=5)
    print("[Dispatcher] Background dispatcher stopped")

def parse_tasks(output):
    tasks = []
    lines = output.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('SLUG') or 'Current board' in line:
            continue
        parts = line.split()
        if len(parts) >= 4:
            status_icon = parts[0]
            task_id = parts[1]
            status = parts[2]
            assignee = parts[3]
            title = ' '.join(parts[4:]) if len(parts) > 4 else ''
            tasks.append({
                'id': task_id,
                'status': status,
                'assignee': assignee,
                'title': title,
                'completed': status_icon == '✓'
            })
    return tasks

def parse_show(output):
    data = {'events': [], 'runs': []}
    lines = output.strip().split('\n')
    current_section = None
    for line in lines:
        line = line.strip()
        if 'Events' in line:
            current_section = 'events'
            continue
        elif 'Runs' in line:
            current_section = 'runs'
            continue
        if current_section == 'events' and line and line.startswith('['):
            data['events'].append(line)
        elif current_section == 'runs' and line and line.startswith('#'):
            data['runs'].append(line)
    return data

# Embedded PWA files
MANIFEST = {
    "name": "Hermes Kanban",
    "short_name": "Hermes",
    "description": "Multi-Agent Kanban Dashboard for Hermes AI",
    "start_url": "/",
    "display": "standalone",
    "orientation": "portrait-primary",
    "background_color": "#000000",
    "theme_color": "#000000",
    "scope": "/",
    "icons": [{
        "src": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect fill='%231a1a2e' width='100' height='100' rx='22'/%3E%3Ctext x='50%25' y='55%25' dominant-baseline='middle' text-anchor='middle' font-size='50'%3E%F0%9F%93%8B%3C/text%3E%3C/svg%3E",
        "sizes": "any",
        "type": "image/svg+xml",
        "purpose": "any maskable"
    }],
    "categories": ["productivity", "business"]
}

SW_JS = """const CACHE_NAME = 'hermes-kanban-v1';
const STATIC_ASSETS = ['/', '/manifest.json', '/api/tasks', '/api/stats', '/api/assignees'];

self.addEventListener('install', event => {
    event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting()));
}

self.addEventListener('activate', event => {
    event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))).then(() => self.clients.claim()));
}

self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    if (request.method !== 'GET') return;
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(fetch(request).then(response => { if (response.ok) { const cloned = response.clone(); caches.open(CACHE_NAME).then(cache => cache.put(request, cloned)); } return response; }).catch(() => caches.match(request)));
        return;
    }
    event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => { if (response.ok) { const cloned = response.clone(); caches.open(CACHE_NAME).then(cache => cache.put(request, cloned)); } return response; })));
}

self.addEventListener('sync', event => { if (event.tag === 'sync-tasks') event.waitUntil(syncTasks()); });
async function syncTasks() { const cache = await caches.open('offline-tasks'); const requests = await cache.keys(); for (const request of requests) { try { await fetch(request); await cache.delete(request); } catch (e) {} } }
self.addEventListener('push', event => { if (!event.data) return; const data = event.data.json(); const options = { body: data.body, icon: '/static/icon-192.png', badge: '/static/badge-72.png', vibrate: [200, 100, 200], data: data.url || '/', actions: [{ action: 'open', title: 'Open' }, { action: 'dismiss', title: 'Dismiss' }] }; event.waitUntil(self.registration.showNotification(data.title, options)); });
self.addEventListener('notificationclick', event => { event.notification.close(); if (event.action === 'open' || !event.action) { event.waitUntil(clients.matchAll({ type: 'window' }).then(clientList => { for (const client of clientList) { if (client.url === event.notification.data && 'focus' in client) return client.focus(); } return clients.openWindow(event.notification.data || '/'); })); } });"""

# Main routes
@app.route('/')
def index():
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/api/tasks')
def get_tasks():
    stdout, stderr, code = run_hermes(['kanban', 'list'])
    if code != 0:
        return jsonify({'error': stderr}), 500
    tasks = parse_tasks(stdout)
    return jsonify({'tasks': tasks})

@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.get_json()
    title = data.get('title', '')
    assignee = data.get('assignee', 'researcher')
    if not title:
        return jsonify({'error': 'Title required'}), 400
    stdout, stderr, code = run_hermes(['kanban', 'create', title, '--assignee', assignee])
    if code != 0:
        return jsonify({'error': stderr}), 500
    # Trigger immediate dispatch after task creation
    run_kanban_dispatch()
    return jsonify({'success': True, 'output': stdout})

@app.route('/api/tasks/<task_id>')
def get_task(task_id):
    stdout, stderr, code = run_hermes(['kanban', 'show', task_id])
    if code != 0:
        return jsonify({'error': stderr}), 500
    return jsonify({'detail': stdout, 'parsed': parse_show(stdout)})

@app.route('/api/tasks/<task_id>/complete', methods=['POST'])
def complete_task(task_id):
    data = request.get_json()
    summary = data.get('summary', 'Completed via dashboard')
    stdout, stderr, code = run_hermes(['kanban', 'complete', task_id, '--summary', summary])
    if code != 0:
        return jsonify({'error': stderr}), 500
    return jsonify({'success': True, 'output': stdout})

@app.route('/api/assignees')
def get_assignees():
    stdout, stderr, code = run_hermes(['kanban', 'assignees'])
    if code != 0:
        return jsonify({'error': stderr}), 500
    return jsonify({'output': stdout})

@app.route('/api/stats')
def get_stats():
    stdout, stderr, code = run_hermes(['kanban', 'stats'])
    if code != 0:
        return jsonify({'error': stderr}), 500
    return jsonify({'output': stdout})

@app.route('/api/boards')
def get_boards():
    stdout, stderr, code = run_hermes(['kanban', 'boards', 'list'])
    if code != 0:
        return jsonify({'error': stderr}), 500
    return jsonify({'output': stdout})

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'hermes-kanban-dashboard'})

# PWA Routes - Must be at root path for PWA registration
@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Hermes Kanban",
        "short_name": "Hermes",
        "description": "Multi-Agent Kanban Dashboard for Hermes AI",
        "start_url": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#000000",
        "theme_color": "#000000",
        "scope": "/",
        "icons": [{
            "src": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect fill='%231a1a2e' width='100' height='100' rx='22'/%3E%3Ctext x='50%25' y='55%25' dominant-baseline='middle' text-anchor='middle' font-size='50'%3E%F0%9F%93%8B%3C/text%3E%3C/svg%3E",
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any maskable"
        }],
        "categories": ["productivity", "business"]
    })

@app.route('/sw.js')
def service_worker():
    return """const CACHE_NAME = 'hermes-kanban-v1';
const STATIC_ASSETS = ['/', '/manifest.json', '/api/tasks', '/api/stats', '/api/assignees'];

self.addEventListener('install', event => {
    event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
    event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    if (request.method !== 'GET') return;
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(fetch(request).then(response => { if (response.ok) { const cloned = response.clone(); caches.open(CACHE_NAME).then(cache => cache.put(request, cloned)); } return response; }).catch(() => caches.match(request)));
        return;
    }
    event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => { if (response.ok) { const cloned = response.clone(); caches.open(CACHE_NAME).then(cache => cache.put(request, cloned)); } return response; })));
});

self.addEventListener('sync', event => { if (event.tag === 'sync-tasks') event.waitUntil(syncTasks()); });
async function syncTasks() { const cache = await caches.open('offline-tasks'); const requests = await cache.keys(); for (const request of requests) { try { await fetch(request); await cache.delete(request); } catch (e) {} } }
self.addEventListener('push', event => { if (!event.data) return; const data = event.data.json(); const options = { body: data.body, icon: '/static/icon-192.png', badge: '/static/badge-72.png', vibrate: [200, 100, 200], data: data.url || '/', actions: [{ action: 'open', title: 'Open' }, { action: 'dismiss', title: 'Dismiss' }] }; event.waitUntil(self.registration.showNotification(data.title, options)); });
self.addEventListener('notificationclick', event => { event.notification.close(); if (event.action === 'open' || !event.action) { event.waitUntil(clients.matchAll({ type: 'window' }).then(clientList => { for (const client of clientList) { if (client.url === event.notification.data && 'focus' in client) return client.focus(); } return clients.openWindow(event.notification.data || '/'); })); } });""", 200, {'Content-Type': 'application/javascript'}

if __name__ == '__main__':
    os.makedirs(STATIC_FOLDER, exist_ok=True)
    # Start background dispatcher
    start_dispatcher()
    # Use PORT from environment (Render sets this to 10000)
    port = int(os.environ.get("PORT", 9121))
    print(f"Starting Kanban Dashboard on http://0.0.0.0:{port}")
    print("Press Ctrl+C to stop")
    try:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    finally:
        stop_dispatcher()
# Enhanced parsing functions
def parse_show(output):
    data = {'events': [], 'runs': [], 'artifacts': [], 'gates': {}, 'description': '', 'dependencies': [], 'pipeline_mode': 'feature', 'priority': 'medium'}
    lines = output.strip().split('\n')
    current_section = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if 'Events' in line:
            current_section = 'events'
            continue
        elif 'Runs' in line:
            current_section = 'runs'
            continue
        elif 'Artifacts' in line:
            current_section = 'artifacts'
            continue
        elif 'Gates' in line or 'Quality Gates' in line:
            current_section = 'gates'
            continue
        elif 'Description' in line or 'Context' in line:
            current_section = 'description'
            continue
        elif 'Dependencies' in line:
            current_section = 'dependencies'
            continue
        elif 'Pipeline Mode' in line:
            current_section = 'pipeline_mode'
            continue
        elif 'Priority' in line:
            current_section = 'priority'
            continue
        if current_section == 'events' and line.startswith('['):
            data['events'].append(line)
        elif current_section == 'runs' and line.startswith('#'):
            data['runs'].append(line)
        elif current_section == 'artifacts' and line:
            data['artifacts'].append({'raw': line})
        elif current_section == 'gates' and ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                data['gates'][parts[0].strip()] = parts[1].strip()
        elif current_section == 'description' and line:
            data['description'] = line
        elif current_section == 'dependencies' and line:
            data['dependencies'] = [d.strip() for d in line.split(',')]
        elif current_section == 'pipeline_mode' and line:
            data['pipeline_mode'] = line.lower()
        elif current_section == 'priority' and line:
            data['priority'] = line.lower()
    return data


@app.route('/api/tasks/<task_id>/move', methods=['POST'])
def move_task(task_id):
    data = request.get_json()
    new_status = data.get('status', '')
    if not new_status:
        return jsonify({'error': 'Status required'}), 400
    
    # Map new column statuses to hermes kanban statuses
    status_map = {
        'ideas': 'triage',
        'research': 'todo',
        'planning': 'ready',
        'dev': 'running',
        'testing': 'blocked',  # testing uses blocked as intermediate
        'marketing': 'running',
        'ready': 'ready',
        'done': 'done'
    }
    hermes_status = status_map.get(new_status, new_status)
    
    stdout, stderr, code = run_hermes(['kanban', 'move', task_id, '--to', hermes_status])
    if code != 0:
        return jsonify({'error': stderr}), 500
    run_kanban_dispatch()
    return jsonify({'success': True, 'output': stdout, 'new_status': new_status})


@app.route('/api/tasks/<task_id>/assign', methods=['POST'])
def assign_task(task_id):
    data = request.get_json()
    assignee = data.get('assignee', '')
    if not assignee:
        return jsonify({'error': 'Assignee required'}), 400
    
    # Map agent keys to hermes profiles
    assignee_map = {
        'researcher': 'researcher',
        'planning': 'default',
        'coder': 'coder',
        'testing': 'reviewer',
        'default': 'default',
        'marketing-research': 'researcher',
        'marketing-script': 'researcher',
        'marketing-image': 'researcher',
        'marketing-video': 'researcher',
        'marketing-campaign': 'default',
        'marketing-qc': 'reviewer',
        'marketing-outreach': 'default',
        'support': 'default',
        'supervisor': 'default'
    }
    hermes_assignee = assignee_map.get(assignee, assignee)
    
    stdout, stderr, code = run_hermes(['kanban', 'assign', task_id, hermes_assignee])
    if code != 0:
        return jsonify({'error': stderr}), 500
    return jsonify({'success': True, 'output': stdout})


@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.get_json()
    title = data.get('title', '')
    assignee = data.get('assignee', 'researcher')
    priority = data.get('priority', 'medium')
    pipeline_mode = data.get('pipelineMode', 'feature')
    dependencies = data.get('dependencies', [])
    description = data.get('description', '')
    
    if not title:
        return jsonify({'error': 'Title required'}), 400
    
    # Build context with all metadata
    context_parts = [title]
    if description:
        context_parts.append(f"Description: {description}")
    if priority != 'medium':
        context_parts.append(f"Priority: {priority}")
    if pipeline_mode != 'feature':
        context_parts.append(f"Pipeline: {pipeline_mode}")
    if dependencies:
        context_parts.append(f"Depends on: {', '.join(dependencies)}")
    
    full_title = ' | '.join(context_parts)
    
    stdout, stderr, code = run_hermes(['kanban', 'create', full_title, '--assignee', assignee])
    if code != 0:
        return jsonify({'error': stderr}), 500
    run_kanban_dispatch()
    return jsonify({'success': True, 'output': stdout})


@app.route('/api/tasks/<task_id>/detail')
def get_task_detail(task_id):
    stdout, stderr, code = run_hermes(['kanban', 'show', task_id])
    if code != 0:
        return jsonify({'error': stderr}), 500
    return jsonify({'detail': stdout, 'parsed': parse_show(stdout)})

