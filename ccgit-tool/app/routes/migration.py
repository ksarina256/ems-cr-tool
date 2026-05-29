"""
Migration routes - form, execution, results, log viewing
"""

from flask import Blueprint, render_template, request, jsonify, send_from_directory
from migration.migration_engine import MigrationEngine
import yaml
import os
import threading

migration_bp = Blueprint("migration", __name__)

_active_jobs = {}


@migration_bp.route("/", methods=["GET"])
def migration_form():
    """Render the migration configuration form."""
    return render_template("migration_form.html")


@migration_bp.route("/start", methods=["POST"])
def start_migration():
    """Accept form POST and kick off migration in a background thread."""
    form = request.form

    config_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "configs", "config.yaml"
    )
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        config = {}

    config.setdefault("clearcase", {})
    config.setdefault("git", {})
    config.setdefault("migration", {})

    config["clearcase"]["vob_path"] = form.get("vob_path", "")
    config["clearcase"]["baseline"] = form.get("baseline", "")
    config["git"]["output_dir"] = form.get("output_dir", "")
    config["migration"]["repo_name"] = form.get("repo_name", "")
    config["migration"]["dry_run"] = "dry_run" in form
    config["migration"]["preserve_tags"] = "preserve_tags" in form
    config["migration"]["validate"] = "validate" in form

    job_id = f"job_{len(_active_jobs) + 1}"
    _active_jobs[job_id] = {"status": "running", "result": None}

    def _run():
        engine = MigrationEngine(config)
        result = engine.run()
        _active_jobs[job_id]["status"] = "done"
        _active_jobs[job_id]["result"] = result

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return render_template("migration_progress.html", job_id=job_id)


@migration_bp.route("/status/<job_id>")
def job_status(job_id):
    """Polling endpoint for migration status."""
    job = _active_jobs.get(job_id)
    if not job:
        return jsonify({"status": "not_found"}), 404
    return jsonify(job)


@migration_bp.route("/results/<job_id>")
def migration_results(job_id):
    """Show migration results page."""
    job = _active_jobs.get(job_id, {})
    result = job.get("result", {})
    return render_template("migration_results.html", result=result, job_id=job_id)


@migration_bp.route("/logs/<path:filename>")
def view_log(filename):
    """Serve a log file for viewing."""
    logs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
    return send_from_directory(logs_dir, filename, mimetype="text/plain")
