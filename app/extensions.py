"""
Flask extension instances, created here (not bound to an app yet) so that
models.py and the blueprints can import them without circular imports.
They are bound to the actual app inside the application factory in
app/__init__.py.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
