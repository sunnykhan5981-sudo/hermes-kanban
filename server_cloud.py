#!/usr/bin/env python3
"""
Minimal cloud deployment server for Hermes Kanban Dashboard.
Serves static UI without hermes CLI dependency.
"""
import os
from flask import Flask, jsonify, Response

app = Flask(__name__, static_folder='static', static_url_path='/static')
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'hermes-kanban-dashboard', 'mode': 'cloud-ui'})

@app.route('/api/tasks')
def list_tasks():
    return jsonify({'tasks': [], 'mode': 'cloud-ui', 'message': 'Connect local server for full data'})

@app.route('/api/tasks/<task_id>/runs')
def task_runs(task_id):
    return jsonify({'runs': [], 'db': {'latest_run': None}, 'mode': 'cloud-ui'})

@app.route('/api/tasks/<task_id>/delete', methods=['POST'])
def delete_task(task_id):
    return jsonify({'success': True, 'mode': 'cloud-ui', 'message': 'Cloud mode: no local hermes CLI'})

@app.route('/api/tasks/<task_id>/complete', methods=['POST'])
def complete_task(task_id):
    return jsonify({'success': True, 'mode': 'cloud-ui', 'message': 'Cloud mode: no local hermes CLI'})

@app.route('/api/tasks', methods=['POST'])
def create_task():
    return jsonify({'success': True, 'mode': 'cloud-ui', 'message': 'Cloud mode: no local hermes CLI'})

@app.route('/api/move', methods=['POST'])
def move_task():
    return jsonify({'success': True, 'mode': 'cloud-ui', 'message': 'Cloud mode: no local hermes CLI'})

@app.route('/api/boards')
def boards():
    return jsonify({'boards': [], 'mode': 'cloud-ui'})

@app.route('/api/stats')
def stats():
    return jsonify({'stats': {}, 'mode': 'cloud-ui'})

@app.route('/api/assignees')
def assignees():
    return jsonify({'assignees': [], 'mode': 'cloud-ui'})

@app.route('/favicon.ico')
def favicon():
    return Response(status=204)

@app.route('/manifest.json')
def manifest():
    return jsonify({
        'name': 'Project-L Kanban',
        'short_name': 'Kanban',
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#07090f',
        'theme_color': '#00f0ff'
    })

@app.route('/')
def index():
    return app.send_static_file('index.html')

if __name__ == '__main__':
    os.makedirs(STATIC_FOLDER, exist_ok=True)
    port = int(os.environ.get("PORT", 9121))
    print("Starting Kanban Cloud UI on http://0.0.0.0:%d" % port)
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
