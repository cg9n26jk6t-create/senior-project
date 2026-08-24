from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from sqlalchemy import func

from ..extensions import db
from ..decorators import role_required
from ..models import User, MechanicProfile, ServiceRequest, Rating, Complaint
from ..constants import STATUS_LABELS

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@role_required("admin")
def dashboard():
    total_requests = ServiceRequest.query.count()
    completed_jobs = ServiceRequest.query.filter(ServiceRequest.status.in_(["completed", "paid", "rated"])).count()
    # Two different numbers on purpose: gross_job_value is the full amount
    # customers have paid; platform_revenue is only RoadRescue's commission
    # out of that (see PLATFORM_COMMISSION_RATE) -- the rest goes to
    # mechanics as their payout. Showing both avoids the confusing
    # impression that the platform "keeps" the full job cost.
    gross_job_value = (
        db.session.query(func.coalesce(func.sum(ServiceRequest.cost), 0))
        .filter(ServiceRequest.status.in_(["paid", "rated"]))
        .scalar()
    )
    platform_revenue = (
        db.session.query(func.coalesce(func.sum(ServiceRequest.platform_fee), 0))
        .filter(ServiceRequest.status.in_(["paid", "rated"]))
        .scalar()
    )
    avg_rating_row = db.session.query(func.avg(Rating.stars)).scalar()
    average_rating = round(avg_rating_row, 1) if avg_rating_row else None
    active_mechanics = MechanicProfile.query.filter_by(status="approved").count()
    pending_approvals = MechanicProfile.query.filter_by(status="pending").count()
    open_complaints = Complaint.query.filter_by(status="open").count()

    return render_template(
        "admin/dashboard.html",
        total_requests=total_requests,
        completed_jobs=completed_jobs,
        gross_job_value=gross_job_value,
        platform_revenue=platform_revenue,
        average_rating=average_rating,
        active_mechanics=active_mechanics,
        pending_approvals=pending_approvals,
        open_complaints=open_complaints,
    )


@admin_bp.route("/mechanics")
@role_required("admin")
def mechanics():
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status", "").strip()
    query_text = request.args.get("q", "").strip()

    query = MechanicProfile.query.join(User)
    if status_filter:
        query = query.filter(MechanicProfile.status == status_filter)
    if query_text:
        like = f"%{query_text}%"
        query = query.filter(db.or_(User.name.ilike(like), User.email.ilike(like)))

    pagination = query.order_by(MechanicProfile.status.asc(), User.name.asc()).paginate(
        page=page, per_page=10, error_out=False
    )
    return render_template(
        "admin/mechanics.html", pagination=pagination, status_filter=status_filter, query_text=query_text
    )


def _mechanic_or_404(mechanic_id):
    return MechanicProfile.query.get_or_404(mechanic_id)


@admin_bp.route("/mechanics/<int:mechanic_id>/approve", methods=["POST"])
@role_required("admin")
def approve_mechanic(mechanic_id):
    profile = _mechanic_or_404(mechanic_id)
    if profile.status != "pending":
        flash("Only a pending application can be approved.", "error")
    else:
        profile.status = "approved"
        db.session.commit()
        flash(f"{profile.user.name} approved as a mechanic.", "success")
    return redirect(url_for("admin.mechanics"))


@admin_bp.route("/mechanics/<int:mechanic_id>/reject", methods=["POST"])
@role_required("admin")
def reject_mechanic(mechanic_id):
    profile = _mechanic_or_404(mechanic_id)
    if profile.status != "pending":
        flash("Only a pending application can be rejected.", "error")
    else:
        profile.status = "unregistered"
        db.session.commit()
        flash(f"{profile.user.name}'s application was rejected.", "info")
    return redirect(url_for("admin.mechanics"))


@admin_bp.route("/mechanics/<int:mechanic_id>/suspend", methods=["POST"])
@role_required("admin")
def suspend_mechanic(mechanic_id):
    profile = _mechanic_or_404(mechanic_id)
    if profile.status != "approved":
        flash("Only an approved mechanic can be suspended.", "error")
    else:
        profile.status = "suspended"
        profile.available = False
        db.session.commit()
        flash(f"{profile.user.name} has been suspended.", "info")
    return redirect(url_for("admin.mechanics"))


@admin_bp.route("/mechanics/<int:mechanic_id>/reactivate", methods=["POST"])
@role_required("admin")
def reactivate_mechanic(mechanic_id):
    profile = _mechanic_or_404(mechanic_id)
    if profile.status != "suspended":
        flash("Only a suspended mechanic can be reactivated.", "error")
    else:
        profile.status = "approved"
        db.session.commit()
        flash(f"{profile.user.name} has been reactivated.", "success")
    return redirect(url_for("admin.mechanics"))


@admin_bp.route("/requests")
@role_required("admin")
def requests_list():
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status", "").strip()

    query = ServiceRequest.query
    if status_filter:
        query = query.filter(ServiceRequest.status == status_filter)

    pagination = query.order_by(ServiceRequest.created_at.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template(
        "admin/requests.html", pagination=pagination, STATUS_LABELS=STATUS_LABELS, status_filter=status_filter
    )


@admin_bp.route("/customers")
@role_required("admin")
def customers():
    page = request.args.get("page", 1, type=int)
    query_text = request.args.get("q", "").strip()

    query = User.query.filter_by(role="customer")
    if query_text:
        like = f"%{query_text}%"
        query = query.filter(db.or_(User.name.ilike(like), User.email.ilike(like)))

    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template("admin/customers.html", pagination=pagination, query_text=query_text)


@admin_bp.route("/complaints")
@role_required("admin")
def complaints():
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status", "").strip()

    query = Complaint.query
    if status_filter:
        query = query.filter(Complaint.status == status_filter)

    pagination = query.order_by(Complaint.status.asc(), Complaint.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    return render_template("admin/complaints.html", pagination=pagination, status_filter=status_filter)


@admin_bp.route("/complaints/<int:complaint_id>/resolve", methods=["POST"])
@role_required("admin")
def resolve_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    complaint.status = "resolved"
    db.session.commit()
    flash("Complaint marked as resolved.", "success")
    return redirect(url_for("admin.complaints"))
