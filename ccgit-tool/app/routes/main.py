"""
Main routes - dashboard and index
"""

from flask import Blueprint, render_template
from migration.migration_engine import MigrationEngine
import os
import json

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Main dashboard."""
    recent = _load_recent_migrations()
    return render_template("dashboard.html", recent_migrations=recent)


def _load_recent_migrations():
    """Load recent migration summaries from the reports directory."""
    reports_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports")
    migrations = []

    if not os.path.exists(reports_dir):
        return migrations

    for fname in sorted(os.listdir(reports_dir), reverse=True)[:5]:
        if fname.endswith(".json"):
            try:
                with open(os.path.join(reports_dir, fname)) as f:
                    migrations.append(json.load(f))
            except Exception:
                continue

    return migrations
