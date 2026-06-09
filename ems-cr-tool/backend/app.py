"""
EMS CR Validation Tool - Flask Backend
Serves the React front end and exposes REST endpoints for running
comparisons, managing CR mappings, and retrieving results.
"""

import os
import json
import zipfile
import shutil
import threading
from flask import Flask, jsonify, request, send_from_directory
from compare_engine import run_comparison

app = Flask(__name__, static_folder="../frontend/build", static_url_path="/")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR   = os.path.dirname(BASE_DIR)
INPUT_DIR     = os.path.join(PROJECT_DIR, "input")
SOURCE_DIR    = os.path.join(INPUT_DIR, "clearcase")
TARGET_DIR    = os.path.join(INPUT_DIR, "gitea")
RESULTS_FILE  = os.path.join(PROJECT_DIR, "last_results.json")
MAPPINGS_FILE = os.path.join(PROJECT_DIR, "cr_mappings.json")
STATUS_FILE   = os.path.join(PROJECT_DIR, "run_status.json")

# Ensure directories exist
os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(TARGET_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_mappings():
    if os.path.exists(MAPPINGS_FILE):
        with open(MAPPINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_mappings(mappings):
    with open(MAPPINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(mappings, f, indent=2)


def _set_status(state, message, progress=0):
    status = {"state": state, "message": message, "progress": progress}
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f)
    return status


def _get_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"state": "idle", "message": "", "progress": 0}


def _dir_has_files(path):
    """Return True if directory exists and contains at least one file."""
    if not os.path.isdir(path):
        return False
    for _, _, files in os.walk(path):
        if files:
            return True
    return False


def _extract_zip_to(zip_path, dest_dir):
    """Extract a zip archive into dest_dir, clearing it first."""
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest_dir)


# ---------------------------------------------------------------------------
# Background comparison runner
# ---------------------------------------------------------------------------

def _run_comparison_thread(source, target, cr_mappings):
    try:
        _set_status("running", "Scanning ClearCase source directory...", 10)

        # Monkey-patch print to update progress messages
        original_print = __builtins__["print"] if isinstance(__builtins__, dict) else print
        step_messages = {
            "[1/6]": ("Scanning ClearCase source directory...", 10),
            "[2/6]": ("Scanning Gitea target directory...", 22),
            "[3/6]": ("Detecting added, removed, modified files...", 38),
            "[4/6]": ("Running line-level diffs...", 58),
            "[5/6]": ("Resolving CR mappings and status...", 80),
            "[6/6]": ("Building final report...", 93),
        }

        import builtins
        original_print = builtins.print

        def progress_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            for prefix, (status_msg, pct) in step_messages.items():
                if msg.startswith(prefix):
                    _set_status("running", status_msg, pct)
                    break
            original_print(*args, **kwargs)

        builtins.print = progress_print

        result = run_comparison(source, target, cr_mappings)

        builtins.print = original_print

        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        _set_status("complete", "Comparison complete.", 100)

    except Exception as e:
        import traceback
        import builtins
        builtins.print = original_print if 'original_print' in dir() else print
        _set_status("error", f"Error: {str(e)}", 0)
        print(f"Comparison error: {traceback.format_exc()}")


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/api/status", methods=["GET"])
def get_status():
    """Check current comparison run status."""
    return jsonify(_get_status())


@app.route("/api/inputs", methods=["GET"])
def get_inputs():
    """Check whether input directories have files loaded."""
    return jsonify({
        "clearcase": _dir_has_files(SOURCE_DIR),
        "gitea": _dir_has_files(TARGET_DIR),
        "sourceDir": SOURCE_DIR,
        "targetDir": TARGET_DIR,
    })


@app.route("/api/upload/<side>", methods=["POST"])
def upload_zip(side):
    """
    Upload a zip file for either 'clearcase' or 'gitea' side.
    Extracts it into the appropriate input directory.
    """
    if side not in ("clearcase", "gitea"):
        return jsonify({"error": "side must be 'clearcase' or 'gitea'"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename.endswith(".zip"):
        return jsonify({"error": "Only .zip files are supported"}), 400

    dest = SOURCE_DIR if side == "clearcase" else TARGET_DIR
    zip_path = os.path.join(INPUT_DIR, f"{side}_upload.zip")
    f.save(zip_path)

    try:
        _extract_zip_to(zip_path, dest)
        os.remove(zip_path)
        file_count = sum(len(files) for _, _, files in os.walk(dest))
        return jsonify({
            "success": True,
            "message": f"Extracted {file_count} files into {side} input folder.",
            "fileCount": file_count,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/run", methods=["POST"])
def run():
    """Trigger a comparison run in a background thread."""
    status = _get_status()
    if status.get("state") == "running":
        return jsonify({"error": "A comparison is already running."}), 409

    if not _dir_has_files(SOURCE_DIR):
        return jsonify({"error": "ClearCase input folder is empty. Please upload a snapshot first."}), 400

    if not _dir_has_files(TARGET_DIR):
        return jsonify({"error": "Gitea input folder is empty. Please upload a snapshot first."}), 400

    cr_mappings = _load_mappings()
    _set_status("running", "Starting comparison...", 0)

    t = threading.Thread(
        target=_run_comparison_thread,
        args=(SOURCE_DIR, TARGET_DIR, cr_mappings),
        daemon=True,
    )
    t.start()

    return jsonify({"success": True, "message": "Comparison started."})


@app.route("/api/results", methods=["GET"])
def get_results():
    """Return the last comparison results."""
    if not os.path.exists(RESULTS_FILE):
        return jsonify({"error": "No results found. Run a comparison first."}), 404

    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Optionally filter by CR or status via query params
    filter_status = request.args.get("status")
    filter_cr = request.args.get("cr")
    search = request.args.get("search", "").lower()

    if filter_status or filter_cr or search:
        files = data.get("files", [])
        if filter_status and filter_status != "all":
            files = [f for f in files if f["status"] == filter_status]
        if filter_cr and filter_cr not in ("all", ""):
            if filter_cr == "none":
                files = [f for f in files if not f.get("cr")]
            else:
                files = [f for f in files if f.get("cr") == filter_cr]
        if search:
            files = [f for f in files
                     if search in f["path"].lower()
                     or search in (f.get("cr") or "").lower()]
        data = {**data, "files": files}

    return jsonify(data)


@app.route("/api/mappings", methods=["GET"])
def get_mappings():
    """Return current CR mappings."""
    return jsonify(_load_mappings())


@app.route("/api/mappings", methods=["POST"])
def save_mappings():
    """Save CR mappings. Body: { "CR-1042": ["path/to/file.py", ...], ... }"""
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object"}), 400
    _save_mappings(data)
    return jsonify({"success": True})


@app.route("/api/mappings/<cr_id>", methods=["DELETE"])
def delete_mapping(cr_id):
    """Delete a single CR mapping."""
    mappings = _load_mappings()
    if cr_id in mappings:
        del mappings[cr_id]
        _save_mappings(mappings)
    return jsonify({"success": True})


@app.route("/api/clear/<side>", methods=["POST"])
def clear_input(side):
    """Clear an input directory (clearcase or gitea)."""
    if side not in ("clearcase", "gitea"):
        return jsonify({"error": "side must be 'clearcase' or 'gitea'"}), 400
    dest = SOURCE_DIR if side == "clearcase" else TARGET_DIR
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Serve React front end for all non-API routes
# ---------------------------------------------------------------------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    frontend_dir = os.path.join(PROJECT_DIR, "frontend")
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return send_from_directory(frontend_dir, "index.html")
    return """
    <html><body style="font-family:sans-serif;padding:2rem">
    <h2>EMS CR Validation Tool — Backend Running</h2>
    <p>Frontend index.html not found. Check the frontend/ folder.</p>
    <p>API endpoints: <a href="/api/status">/api/status</a> |
    <a href="/api/inputs">/api/inputs</a> |
    <a href="/api/results">/api/results</a></p>
    </body></html>
    """


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  EMS CR Validation Tool — Backend Server")
    print("="*55)
    print(f"  Input (ClearCase): {SOURCE_DIR}")
    print(f"  Input (Gitea):     {TARGET_DIR}")
    print(f"  Results:           {RESULTS_FILE}")
    print(f"  CR Mappings:       {MAPPINGS_FILE}")
    print("="*55)
    print("  Open in browser:   http://localhost:5000")
    print("="*55 + "\n")
    app.run(debug=False, port=5000, threaded=True)
