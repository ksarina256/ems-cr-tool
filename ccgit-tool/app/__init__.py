"""
CCGit Tool - Flask Application Factory
"""

from flask import Flask


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = "ccgit-dev-secret-change-in-prod"

    from app.routes.main import main_bp
    from app.routes.migration import migration_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(migration_bp, url_prefix="/migration")

    return app
