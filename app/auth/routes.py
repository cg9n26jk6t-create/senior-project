from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db
from ..models import User, MechanicProfile
from ..email_utils import send_email
from .forms import RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower().strip()).first():
            flash("An account with that email already exists.", "error")
            return render_template("auth/register.html", form=form)

        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip(),
            phone=form.phone.data.strip(),
            role=form.role.data,
        )
        user.set_password(form.password.data)
        user.login_count = 1  # registering logs them straight in -- this counts as login #1
        db.session.add(user)
        db.session.flush()  # assigns user.id before we reference it below

        if user.role == "mechanic":
            profile = MechanicProfile(user_id=user.id, status="unregistered")
            db.session.add(profile)

        db.session.commit()

        login_user(user)
        if user.role == "mechanic":
            flash("Welcome! Submit your certifications next so an admin can review your application.", "success")
            return redirect(url_for("mechanic.apply"))
        flash("Welcome to RoadRescue!", "success")
        return redirect(url_for("customer.dashboard"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user is None or not user.check_password(form.password.data):
            flash("Incorrect email or password.", "error")
            return render_template("auth/login.html", form=form)

        user.login_count += 1
        db.session.commit()

        login_user(user, remember=form.remember_me.data)
        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user:
            token = user.generate_reset_token()
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            body = (
                f"Hi {user.name},\n\n"
                "Someone (hopefully you) asked to reset your RoadRescue password. "
                f"This link is valid for one hour:\n\n{reset_url}\n\n"
                "If you didn't request this, you can safely ignore this email."
            )
            sent = False
            try:
                sent = send_email(user.email, "Reset your RoadRescue password", body)
            except Exception:
                # A misconfigured/unreachable SMTP server shouldn't block the
                # reset flow -- fall through to showing the link directly,
                # same as when no mail server is configured at all.
                sent = False

            if not sent:
                flash(
                    f"No email server is configured, so here is your reset link directly (dev mode): {reset_url}",
                    "info",
                )

        # Same message whether or not the email matched an account, so this
        # page can't be used to check which emails are registered.
        flash("If that email is registered, a password reset link has been sent.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    user = User.verify_reset_token(token, max_age=current_app.config["PASSWORD_RESET_MAX_AGE_SECONDS"])
    if user is None:
        flash("That reset link is invalid or has expired. Request a new one below.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been updated. Log in with your new password.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)
