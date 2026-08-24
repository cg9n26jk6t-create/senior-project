"""
Application configuration.

Only the SQLALCHEMY_DATABASE_URI needs to change to move from local SQLite
development to a production PostgreSQL database, e.g.:

    DATABASE_URL=postgresql://user:password@host:5432/roadrescue

Everything else (models, queries, migrations) is written against the
SQLAlchemy ORM and is database-agnostic.
"""

import os

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    """Base configuration shared by every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "instance", "roadrescue.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Stripe test-mode keys. Leave blank to fall back to the built-in
    # "simulated payment" flow, which requires no external account at all.
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

    WTF_CSRF_ENABLED = True

    # Picks up template edits without restarting `flask run` during development.
    TEMPLATES_AUTO_RELOAD = True

    # Where mechanic certification documents are stored, and the hard cap
    # Flask enforces on any incoming request body (keeps someone from
    # uploading a huge file and exhausting disk/memory).
    UPLOAD_FOLDER = os.path.join(basedir, "instance", "uploads", "certifications")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB


class TestingConfig(Config):
    """Configuration used by the pytest suite: isolated in-memory database."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
