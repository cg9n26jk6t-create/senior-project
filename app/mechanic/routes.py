import os
import uuid

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app, send_from_directory
from flask_login import login_required, current_user

from ..extensions import db
from ..decorators import role_required, approved_mechanic_required
from ..models import ServiceRequest, Certification, distance_between_km
from ..constants import STATUS_LABELS, URGENT_SURCHARGE, LEBANON_MAP_CENTER, LEBANON_MAP_DEFAULT_ZOOM
from .forms import CertificationForm, ProfileForm

mechanic_bp = Blueprint("mechanic", __name__, url_prefix="/mechanic")


@mechanic_bp.route("/dashboard")
@role_required("mechanic")
def dashboard():
    profile = current_user.mechanic_profile
    pending_count = 0
    active_job = None
    if profile.status == "approved":
        pending_count = (
            ServiceRequest.query.filter_by(status="pending")
            .filter(~ServiceRequest.declined_by.contains(str(profile.id)))
            .count()
        )
        active_job = (
            ServiceRequest.query.filter(
                ServiceRequest.mechanic_id == profile.id,
                ServiceRequest.status.in_(["accepted", "enroute", "arrived", "inprogress"]),
            )
            .order_by(ServiceRequest.updated_at.desc())
            .first()
        )
        if active_job:
            active_job.refresh_tracking()
            db.session.commit()
    return render_template(
        "mechanic/dashboard.html",
        profile=profile,
        pending_count=pending_count,
        active_job=active_job,
        STATUS_LABELS=STATUS_LABELS,
        map_center=LEBANON_MAP_CENTER,
        map_zoom=LEBANON_MAP_DEFAULT_ZOOM,
    )


@mechanic_bp.route("/location", methods=["POST"])
@approved_mechanic_required
def update_location():
    """
    Lets a mechanic set their current position so incoming on-demand
    requests can be sorted by distance -- see incoming_requests() below.
    """
    profile = current_user.mechanic_profile
    lat = request.form.get("latitude")
    lng = request.form.get("longitude")
    if not lat or not lng:
        flash("Drop a pin on the map to set your location.", "error")
        return redirect(url_for("mechanic.dashboard"))
    profile.current_lat = float(lat)
    profile.current_lng = float(lng)
    db.session.commit()
    flash("Your location has been updated.", "success")
    return redirect(url_for("mechanic.dashboard"))


@mechanic_bp.route("/apply", methods=["GET", "POST"])
@role_required("mechanic")
def apply():
    profile = current_user.mechanic_profile
    if profile.status == "approved":
        flash("You are already an approved mechanic.", "info")
        return redirect(url_for("mechanic.dashboard"))
    if profile.status == "suspended":
        flash("Your account is suspended. Contact an administrator.", "error")
        return redirect(url_for("mechanic.dashboard"))

    form = CertificationForm()
    if form.validate_on_submit():
        upload = form.document.data
        original_name = os.path.basename(upload.filename)
        extension = original_name.rsplit(".", 1)[1].lower()
        stored_name = f"{uuid.uuid4().hex}.{extension}"
        upload.save(os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name))

        db.session.add(
            Certification(mechanic_id=profile.id, original_filename=original_name, stored_filename=stored_name)
        )
        if profile.status == "unregistered":
            profile.status = "pending"
        db.session.commit()
        flash("Certification uploaded. You're waitlisted for admin review.", "success")
        return redirect(url_for("mechanic.apply"))

    return render_template("mechanic/apply.html", form=form, profile=profile)


@mechanic_bp.route("/certifications/<int:cert_id>/file")
@login_required
def certification_file(cert_id):
    """Serves an uploaded certification document to its owning mechanic or any admin."""
    cert = Certification.query.get_or_404(cert_id)
    is_owner = current_user.role == "mechanic" and current_user.mechanic_profile.id == cert.mechanic_id
    if not (is_owner or current_user.role == "admin"):
        abort(403)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"], cert.stored_filename, download_name=cert.original_filename
    )


@mechanic_bp.route("/certifications/<int:cert_id>/delete", methods=["POST"])
@role_required("mechanic")
def delete_certification(cert_id):
    cert = Certification.query.get_or_404(cert_id)
    if cert.mechanic_id != current_user.mechanic_profile.id:
        abort(403)
    stored_path = os.path.join(current_app.config["UPLOAD_FOLDER"], cert.stored_filename)
    if os.path.exists(stored_path):
        os.remove(stored_path)
    db.session.delete(cert)
    db.session.commit()
    flash("Certification removed.", "info")
    return redirect(url_for("mechanic.apply"))


@mechanic_bp.route("/availability/toggle", methods=["POST"])
@approved_mechanic_required
def toggle_availability():
    profile = current_user.mechanic_profile
    profile.available = not profile.available
    db.session.commit()
    flash("You are now " + ("available" if profile.available else "offline") + ".", "success")
    return redirect(url_for("mechanic.dashboard"))


@mechanic_bp.route("/requests")
@approved_mechanic_required
def incoming_requests():
    profile = current_user.mechanic_profile

    # Appointments booked specifically with this mechanic, plus any that
    # were booked with someone else but released back to the pool after a
    # decline (see ServiceRequest.release) -- those still need a home, or
    # they'd be invisible to every mechanic once their original pick fell
    # through.
    appointments = (
        ServiceRequest.query.filter_by(status="pending", service_mode="appointment")
        .filter(db.or_(ServiceRequest.mechanic_id == profile.id, ServiceRequest.mechanic_id.is_(None)))
        .filter(~ServiceRequest.declined_by.contains(str(profile.id)))
        .order_by(ServiceRequest.appointment_date.asc())
        .all()
    )

    # Open, on-demand requests any available mechanic can pick up.
    on_demand = (
        ServiceRequest.query.filter_by(status="pending", mechanic_id=None, service_mode="on_demand")
        .filter(~ServiceRequest.declined_by.contains(str(profile.id)))
        .order_by(ServiceRequest.urgent.desc(), ServiceRequest.created_at.asc())
        .all()
    )

    # Nearest-first, so a mechanic sees the jobs they can realistically
    # reach quickest at the top of the list -- only possible once both the
    # mechanic and the request have a map pin to measure between.
    if profile.current_lat is not None and profile.current_lng is not None:
        def _distance(r):
            if r.customer_lat is None or r.customer_lng is None:
                return float("inf")
            return distance_between_km(profile.current_lat, profile.current_lng, r.customer_lat, r.customer_lng)

        for r in on_demand:
            r.distance_from_me_km = None if r.customer_lat is None else round(_distance(r), 1)
        on_demand.sort(key=_distance)
    else:
        for r in on_demand:
            r.distance_from_me_km = None

    return render_template(
        "mechanic/requests.html", appointments=appointments, on_demand=on_demand, has_location=profile.current_lat is not None
    )


def _assigned_job_or_404(request_id):
    svc_request = ServiceRequest.query.get_or_404(request_id)
    if svc_request.mechanic_id != current_user.mechanic_profile.id:
        abort(403)
    return svc_request


@mechanic_bp.route("/requests/<int:request_id>/accept", methods=["POST"])
@approved_mechanic_required
def accept_request(request_id):
    svc_request = ServiceRequest.query.get_or_404(request_id)
    try:
        svc_request.accept(current_user.mechanic_profile)
        db.session.commit()
        flash("Job accepted. Update its status as you make progress.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("mechanic.job_detail", request_id=svc_request.id))


@mechanic_bp.route("/requests/<int:request_id>/decline", methods=["POST"])
@approved_mechanic_required
def decline_request(request_id):
    svc_request = ServiceRequest.query.get_or_404(request_id)
    profile = current_user.mechanic_profile
    was_appointment = svc_request.mechanic_id == profile.id
    svc_request.add_decline(profile.id)
    svc_request.release(profile)
    db.session.commit()
    if was_appointment:
        flash("Appointment declined. It's now open for another mechanic to accept.", "info")
    else:
        flash("Request declined.", "info")
    return redirect(url_for("mechanic.incoming_requests"))


@mechanic_bp.route("/jobs/<int:request_id>")
@approved_mechanic_required
def job_detail(request_id):
    svc_request = _assigned_job_or_404(request_id)
    svc_request.refresh_tracking()
    db.session.commit()
    return render_template(
        "mechanic/job_detail.html", r=svc_request, STATUS_LABELS=STATUS_LABELS, URGENT_SURCHARGE=URGENT_SURCHARGE
    )


@mechanic_bp.route("/jobs/<int:request_id>/advance", methods=["POST"])
@approved_mechanic_required
def advance_job(request_id):
    svc_request = _assigned_job_or_404(request_id)
    profile = current_user.mechanic_profile
    try:
        if svc_request.status == "inprogress":
            svc_request.mark_completed(profile)
            flash("Job marked as completed. The customer can now pay.", "success")
        else:
            svc_request.advance(profile)
            flash(f"Status updated to '{STATUS_LABELS[svc_request.status]}'.", "success")
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("mechanic.job_detail", request_id=svc_request.id))


@mechanic_bp.route("/jobs")
@approved_mechanic_required
def job_history():
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status", "").strip()

    query = ServiceRequest.query.filter_by(mechanic_id=current_user.mechanic_profile.id)
    if status_filter:
        query = query.filter(ServiceRequest.status == status_filter)

    pagination = query.order_by(ServiceRequest.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template(
        "mechanic/jobs.html", pagination=pagination, STATUS_LABELS=STATUS_LABELS, status_filter=status_filter
    )


@mechanic_bp.route("/profile", methods=["GET", "POST"])
@role_required("mechanic")
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data.strip()
        current_user.phone = form.phone.data.strip()
        if form.new_password.data:
            current_user.set_password(form.new_password.data)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("mechanic.profile"))
    return render_template("mechanic/profile.html", form=form)
