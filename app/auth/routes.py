from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db
from ..models import User, MechanicProfile
from .forms import RegisterForm, LoginForm

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
