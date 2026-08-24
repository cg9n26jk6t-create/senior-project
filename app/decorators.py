"""
Server-side role-based access control. Every role-restricted route in the
customer/mechanic/admin blueprints is wrapped with one of these -- hiding a
link in a template is never sufficient on its own.
"""

from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def role_required(*roles):
    """Require login AND that current_user.role is one of the given roles."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def approved_mechanic_required(view):
    """
    Require an approved (not pending/suspended/unregistered) mechanic.
    Use on top of role_required("mechanic") for job-handling routes --
    a mechanic still needs to reach their own dashboard while pending.
    """

    @wraps(view)
    @role_required("mechanic")
    def wrapped(*args, **kwargs):
        profile = current_user.mechanic_profile
        if profile is None or profile.status != "approved":
            abort(403)
        return view(*args, **kwargs)

    return wrapped
