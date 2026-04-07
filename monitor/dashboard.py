"""
Flask dashboard server for pipeline monitoring and triggering.

Provides:
  - SSE stream at /sse
  - Event ingestion at /api/events (POST)
  - Run management at /api/runs/* (POST/GET)
  - Config management at /api/config (GET/POST)
  - Pipeline trigger at /api/trigger (POST)
  - Health check at /health

Run standalone:
    python -m monitor.dashboard
"""
import json
import os
import subprocess
import sys
import threading
import time
import queue
from pathlib import Path

from flask import Flask, Response, jsonify, request, render_template

from monitor.events import PipelineEvent
from monitor.run_store import get_run_store, RunStore
from monitor.config_manager import get_config_manager, ConfigManager


def create_app(run_store: RunStore | None = None, config_manager: ConfigManager | None = None) -> Flask:
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    app = Flask(__name__, template_folder=template_dir)

    # Use provided or global instances
    _run_store = run_store or get_run_store()
    _config = config_manager or get_config_manager()

    # SSE subscriber queues
    _sse_queues: list[queue.Queue] = []
    _sse_lock = threading.Lock()

    # ─── SSE Endpoint ──────────────────────────────────────────────────

    @app.route("/sse")
    def sse():
        """SSE stream: clients receive pipeline events in real-time."""
        q: queue.Queue = queue.Queue(maxsize=500)

        def generate():
            with _sse_lock:
                _sse_queues.append(q)
            try:
                while True:
                    try:
                        event = q.get(timeout=30)
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    except queue.Empty:
                        yield f": ping\n\n"
            except GeneratorExit:
                with _sse_lock:
                    if q in _sse_queues:
                        _sse_queues.remove(q)

        return Response(generate(), mimetype="text/event-stream")

    # ─── Broadcast helper ───────────────────────────────────────────────

    def _broadcast(event_dict: dict) -> None:
        with _sse_lock:
            for q in _sse_queues:
                try:
                    q.put_nowait(event_dict)
                except queue.Full:
                    pass  # Drop if client is slow

    # ─── Event Ingestion ───────────────────────────────────────────────

    @app.route("/api/events", methods=["POST"])
    def ingest_event():
        """Pipeline posts events here."""
        try:
            event_data = request.json
            event = PipelineEvent.from_dict(event_data)
            _run_store.append_event(event)
            _broadcast(event.to_dict())
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route("/api/runs/start", methods=["POST"])
    def start_run():
        """Pipeline announces a new run has started."""
        try:
            data = request.json
            run_id = data.get("run_id")
            metadata = data.get("metadata", {})
            _run_store.start_run(run_id, metadata)
            # Also notify current SSE clients
            _broadcast({
                "event_id": "announce",
                "type": "run_started",
                "data": {"run_id": run_id, "project_name": metadata.get("project_name", "")},
            })
            return jsonify({"status": "ok", "run_id": run_id})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route("/api/runs/<run_id>/finish", methods=["POST"])
    def finish_run(run_id: str):
        """Pipeline signals run completion."""
        try:
            data = request.json
            status = data.get("status", "completed")
            summary = data.get("summary", {})
            _run_store.finish_run(run_id, status, summary)
            _broadcast({
                "event_id": "announce",
                "type": "run_finished",
                "data": {"run_id": run_id, "status": status},
            })
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    # ─── Run History ────────────────────────────────────────────────────

    @app.route("/api/runs")
    def list_runs():
        return jsonify(_run_store.list_runs(limit=20))

    @app.route("/api/runs/<run_id>")
    def get_run(run_id: str):
        run = _run_store.get_run(run_id)
        if run is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(run)

    @app.route("/api/runs/<run_id>/events")
    def get_run_events(run_id: str):
        return jsonify(_run_store.get_run_events(run_id))

    # ─── Config ────────────────────────────────────────────────────────

    @app.route("/api/config")
    def get_config():
        return jsonify(_config.get_all())

    @app.route("/api/config/reload", methods=["POST"])
    def reload_config():
        _config.reload()
        return jsonify({"status": "reloaded", "config": _config.get_all()})

    @app.route("/api/config/prompt/<name>", methods=["GET"])
    def get_prompt(name: str):
        prompt = _config.get("prompts", {}).get(name, "")
        return jsonify({"name": name, "content": prompt})

    @app.route("/api/config/prompt/<name>", methods=["POST"])
    def save_prompt(name: str):
        content = request.json.get("content", "")
        _config.save_prompt(name, content)
        return jsonify({"status": "saved"})

    @app.route("/api/config/setting/<key>", methods=["POST"])
    def save_setting(key: str):
        value = request.json.get("value")
        _config.save_setting(key, value)
        return jsonify({"status": "saved"})

    # ─── Pipeline Trigger ─────────────────────────────────────────────

    _active_pipeline: dict = {}  # run_id -> {"process": Popen, "started_at": float}

    @app.route("/api/trigger", methods=["POST"])
    def trigger_pipeline():
        """Trigger a new pipeline run from the dashboard."""
        data = request.json or {}
        project_path = data.get("project_path", "").strip()
        if not project_path:
            return jsonify({"error": "project_path is required"}), 400
        if not os.path.isdir(project_path):
            return jsonify({"error": f"Directory not found: {project_path}"}), 400

        # Kill existing active pipeline if any
        for rid, info in list(_active_pipeline.items()):
            proc = info.get("process")
            if proc and proc.poll() is None:
                proc.terminate()
            del _active_pipeline[rid]

        # Start new pipeline as subprocess
        project_name = os.path.basename(os.path.abspath(project_path))
        run_id = time.strftime("%Y-%m-%d_%H-%M-%S") + "_" + os.urandom(4).hex()

        # Start run in run_store
        _run_store.start_run(run_id, {
            "project_path": project_path,
            "project_name": project_name,
            "provider": _config.provider,
            "models": {
                "lite": _config.model_lite,
                "pro": _config.model_pro,
                "max": _config.model_max,
            },
        })

        # Notify SSE clients about new run
        _broadcast({
            "event_id": "announce",
            "type": "run_started",
            "data": {"run_id": run_id, "project_name": project_name, "status": "running"},
        })

        # Start the pipeline subprocess
        main_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        proc = subprocess.Popen(
            [sys.executable, main_py, project_path, "--monitor"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        _active_pipeline[run_id] = {
            "process": proc,
            "project_path": project_path,
            "project_name": project_name,
            "started_at": time.time(),
        }

        return jsonify({"status": "started", "run_id": run_id, "project_name": project_name})

    @app.route("/api/trigger/status")
    def trigger_status():
        """Get status of active pipeline."""
        if not _active_pipeline:
            return jsonify({"running": False})
        rid, info = list(_active_pipeline.items())[0]
        proc = info["process"]
        return jsonify({
            "running": proc.poll() is None,
            "run_id": rid,
            "project_name": info["project_name"],
            "elapsed_s": time.time() - info["started_at"],
        })

    @app.route("/api/trigger/kill", methods=["POST"])
    def kill_pipeline():
        """Kill the active pipeline."""
        for rid, info in _active_pipeline.items():
            proc = info.get("process")
            if proc and proc.poll() is None:
                proc.terminate()
                time.sleep(0.5)
                if proc.poll() is None:
                    proc.kill()
        _active_pipeline.clear()
        return jsonify({"status": "killed"})

    # ─── Dashboard UI (3 pages) ─────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template("monitor.html")

    @app.route("/monitor")
    def monitor_page():
        return render_template("monitor.html")

    @app.route("/config")
    def config_page():
        return render_template("config.html")

    @app.route("/trigger")
    def trigger_page():
        return render_template("trigger.html")

    # ─── Health ────────────────────────────────────────────────────────

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "timestamp": time.time()})

    return app


def main():
    app = create_app()
    app.run(host="0.0.0.0", port=7890, debug=False, threaded=True)


if __name__ == "__main__":
    main()
