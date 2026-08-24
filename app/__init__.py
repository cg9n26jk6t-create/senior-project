"""
Application factory. Creating the app here (rather than a bare module-level
`app = Flask(__name__)`) is what lets tests/conftest.py spin up a separate
instance with TestingConfig and its own in-memory database.
"""

import os

from flask import Flask, render_template, redirect, url_for
from flask_login import current_user

from .config import Config
from .extensions import db, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "info"
    csrf.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .auth.routes import auth_bp
    from .customer.routes import customer_bp
    from .mechanic.routes import mechanic_bp
    from .admin.routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(mechanic_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            destination = {
                "customer": "customer.dashboard",
                "mechanic": "mechanic.dashboard",
                "admin": "admin.dashboard",
            }[current_user.role]
            return redirect(url_for(destination))
        return render_template("index.html")

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    # Simple bootstrap for local dev/tests: create tables if they don't
    # exist yet. For a production deployment this would be replaced by a
    # proper migration tool (e.g. Flask-Migrate/Alembic) -- see README.
    with app.app_context():
        db.create_all()

    return app
