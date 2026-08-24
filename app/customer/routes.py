from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user

from ..extensions import db
from ..decorators import role_required
from ..models import Vehicle, ServiceRequest, MechanicProfile, Rating, Complaint
from ..constants import (
    LEBANESE_AREAS,
    ISSUE_TYPES,
    STATUS_LABELS,
    URGENT_SURCHARGE,
    LEBANON_MAP_CENTER,
    LEBANON_MAP_DEFAULT_ZOOM,
)
from .forms import ProfileForm, VehicleForm, ServiceRequestForm, RatingForm, ComplaintForm

customer_bp = Blueprint("customer", __name__, url_prefix="/customer")


def _own_request_or_404(request_id):
    """Fetch a ServiceRequest, but only if it belongs to the current customer."""
    svc_request = ServiceRequest.query.get_or_404(request_id)
    if svc_request.customer_id != current_user.id:
        abort(403)
    return svc_request


@customer_bp.route("/dashboard")
@role_required("customer")
def dashboard():
    active_requests = (
        ServiceRequest.query.filter(
            ServiceRequest.customer_id == current_user.id,
            ServiceRequest.status.notin_(["paid", "rated", "cancelled"]),
        )
        .order_by(ServiceRequest.created_at.desc())
        .all()
    )
    vehicle_count = Vehicle.query.filter_by(customer_id=current_user.id).count()
    return render_template(
        "customer/dashboard.html", active_requests=active_requests, vehicle_count=vehicle_count, STATUS_LABELS=STATUS_LABELS
    )


# ---------------------------------------------------------------- profile

@customer_bp.route("/profile", methods=["GET", "POST"])
@role_required("customer")
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data.strip()
        current_user.phone = form.phone.data.strip()
        if form.new_password.data:
            current_user.set_password(form.new_password.data)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("customer.profile"))
    return render_template("customer/profile.html", form=form)


# ---------------------------------------------------------------- vehicles

@customer_bp.route("/vehicles")
@role_required("customer")
def vehicles():
    my_vehicles = Vehicle.query.filter_by(customer_id=current_user.id).order_by(Vehicle.id.desc()).all()
    return render_template("customer/vehicles.html", vehicles=my_vehicles)


@customer_bp.route("/vehicles/new", methods=["GET", "POST"])
@role_required("customer")
def new_vehicle():
    form = VehicleForm()
    if form.validate_on_submit():
        vehicle = Vehicle(
            customer_id=current_user.id,
            make=form.make.data.strip(),
            model=form.model.data.strip(),
            year=form.year.data,
            plate=form.plate.data.strip().upper(),
        )
        db.session.add(vehicle)
        db.session.commit()
        flash("Vehicle added.", "success")
        return redirect(url_for("customer.vehicles"))
    return render_template("customer/vehicle_form.html", form=form, mode="add", current_year=date.today().year)


@customer_bp.route("/vehicles/<int:vehicle_id>/edit", methods=["GET", "POST"])
@role_required("customer")
def edit_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if vehicle.customer_id != current_user.id:
        abort(403)
    form = VehicleForm(obj=vehicle)
    if form.validate_on_submit():
        vehicle.make = form.make.data.strip()
        vehicle.model = form.model.data.strip()
        vehicle.year = form.year.data
        vehicle.plate = form.plate.data.strip().upper()
        db.session.commit()
        flash("Vehicle updated.", "success")
        return redirect(url_for("customer.vehicles"))
    return render_template(
        "customer/vehicle_form.html", form=form, mode="edit", vehicle=vehicle, current_year=date.today().year
    )


@customer_bp.route("/vehicles/<int:vehicle_id>/delete", methods=["POST"])
@role_required("customer")
def delete_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if vehicle.customer_id != current_user.id:
        abort(403)
    db.session.delete(vehicle)
    db.session.commit()
    flash("Vehicle removed.", "info")
    return redirect(url_for("customer.vehicles"))


# ---------------------------------------------------------------- requests

def _available_mechanics():
    return (
        MechanicProfile.query.filter_by(status="approved", available=True)
        .order_by(MechanicProfile.rating_total.desc())
        .all()
    )


def _mechanic_choice_label(profile):
    rating = f"{profile.average_rating} / 5" if profile.average_rating else "no ratings yet"
    return f"{profile.user.name} ({rating})"


@customer_bp.route("/requests/new", methods=["GET", "POST"])
@role_required("customer")
def new_request():
    my_vehicles = Vehicle.query.filter_by(customer_id=current_user.id).order_by(Vehicle.id.desc()).all()
    if not my_vehicles:
        flash("Add a vehicle before requesting assistance.", "error")
        return redirect(url_for("customer.new_vehicle"))

    form = ServiceRequestForm()
    form.vehicle_id.choices = [(v.id, v.label) for v in my_vehicles]

    available_mechanics = _available_mechanics()
    form.appointment_mechanic_id.choices = [(0, "Select a mechanic")] + [
        (m.id, _mechanic_choice_label(m)) for m in available_mechanics
    ]

    if form.validate_on_submit():
        # A handful of rules depend on other fields' values, which plain
        # WTForms validators can't easily express -- checked by hand here.
        errors = []
        if form.issue_type.data == "other" and not form.details.data.strip():
            errors.append("Please describe the problem when choosing \"Other\".")

        appointment_mechanic = None
        if form.service_mode.data == "appointment":
            if not form.appointment_date.data:
                errors.append("Choose a drop-off date for your appointment.")
            elif form.appointment_date.data < date.today():
                errors.append("The appointment date can't be in the past.")
            if not form.appointment_time_of_day.data:
                errors.append("Choose a preferred time of day for your appointment.")
            if not form.appointment_mechanic_id.data:
                errors.append("Choose a mechanic who is available for your appointment.")
            else:
                appointment_mechanic = next(
                    (m for m in available_mechanics if m.id == form.appointment_mechanic_id.data), None
                )
                if appointment_mechanic is None:
                    errors.append("That mechanic is no longer available -- please choose another.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "customer/request_new.html",
                form=form,
                areas=LEBANESE_AREAS,
                issue_types=ISSUE_TYPES,
                map_center=LEBANON_MAP_CENTER,
                map_zoom=LEBANON_MAP_DEFAULT_ZOOM,
            )

        cost = ServiceRequest.calculate_cost(form.issue_type.data, form.urgent.data)
        svc_request = ServiceRequest(
            customer_id=current_user.id,
            vehicle_id=form.vehicle_id.data,
            issue_type=form.issue_type.data,
            details=form.details.data.strip() if form.details.data else None,
            address=form.address.data.strip(),
            urgent=form.urgent.data,
            status="pending",
            cost=cost,
            service_mode=form.service_mode.data,
            preferred_payment_method=form.preferred_payment_method.data,
        )
        if form.service_mode.data == "appointment":
            svc_request.appointment_date = form.appointment_date.data
            svc_request.appointment_time_of_day = form.appointment_time_of_day.data
            # Pre-assigns the chosen mechanic; they still have to accept it
            # (see ServiceRequest.accept), same as any other pending request.
            svc_request.mechanic_id = appointment_mechanic.id

        # The map pin is optional -- a customer who only typed an address
        # (or has JavaScript disabled) still gets a normal request, just
        # without the live map view later.
        if form.latitude.data and form.longitude.data:
            svc_request.customer_lat = float(form.latitude.data)
            svc_request.customer_lng = float(form.longitude.data)
        db.session.add(svc_request)
        db.session.commit()
        if form.service_mode.data == "appointment":
            flash("Appointment requested! We'll let you know once the mechanic confirms.", "success")
        else:
            flash("Help is on the way to being found! We notified available mechanics.", "success")
        return redirect(url_for("customer.request_detail", request_id=svc_request.id))

    return render_template(
        "customer/request_new.html",
        form=form,
        areas=LEBANESE_AREAS,
        issue_types=ISSUE_TYPES,
        map_center=LEBANON_MAP_CENTER,
        map_zoom=LEBANON_MAP_DEFAULT_ZOOM,
    )


@customer_bp.route("/requests")
@role_required("customer")
def requests_list():
    page = request.args.get("page", 1, type=int)
    pagination = (
        ServiceRequest.query.filter_by(customer_id=current_user.id)
        .order_by(ServiceRequest.created_at.desc())
        .paginate(page=page, per_page=10, error_out=False)
    )
    return render_template("customer/requests.html", pagination=pagination, STATUS_LABELS=STATUS_LABELS)


@customer_bp.route("/requests/<int:request_id>")
@role_required("customer")
def request_detail(request_id):
    svc_request = _own_request_or_404(request_id)
    svc_request.refresh_tracking()
    db.session.commit()
    rating_form = RatingForm()
    complaint_form = ComplaintForm()
    return render_template(
        "customer/request_detail.html",
        r=svc_request,
        STATUS_LABELS=STATUS_LABELS,
        URGENT_SURCHARGE=URGENT_SURCHARGE,
        rating_form=rating_form,
        complaint_form=complaint_form,
        map_zoom=LEBANON_MAP_DEFAULT_ZOOM,
    )


@customer_bp.route("/requests/<int:request_id>/cancel", methods=["POST"])
@role_required("customer")
def cancel_request(request_id):
    svc_request = _own_request_or_404(request_id)
    try:
        svc_request.cancel()
        db.session.commit()
        flash("Request cancelled.", "info")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("customer.request_detail", request_id=svc_request.id))


@customer_bp.route("/requests/<int:request_id>/tracking")
@role_required("customer")
def request_tracking(request_id):
    """Polled by static/js/tracking.js to animate the live mechanic view."""
    svc_request = _own_request_or_404(request_id)
    svc_request.refresh_tracking()
    db.session.commit()
    mechanic_position = svc_request.mechanic_position
    return jsonify(
        status=svc_request.status,
        status_label=STATUS_LABELS[svc_request.status],
        distance_km=svc_request.distance_km,
        eta_minutes=svc_request.eta_minutes,
        mechanic_lat=mechanic_position[0] if mechanic_position else None,
        mechanic_lng=mechanic_position[1] if mechanic_position else None,
    )


def _stripe_keys():
    from flask import current_app

    secret_key = current_app.config.get("STRIPE_SECRET_KEY")
    publishable_key = current_app.config.get("STRIPE_PUBLISHABLE_KEY")
    return secret_key, publishable_key


@customer_bp.route("/requests/<int:request_id>/pay", methods=["GET", "POST"])
@role_required("customer")
def pay_request(request_id):
    svc_request = _own_request_or_404(request_id)
    if svc_request.status != "completed":
        flash("This request isn't ready for payment yet.", "error")
        return redirect(url_for("customer.request_detail", request_id=svc_request.id))

    secret_key, publishable_key = _stripe_keys()
    # Both keys are required: the secret key creates the PaymentIntent
    # server-side, the publishable key lets the browser's Stripe.js render
    # the actual card field. Card payment is a real Stripe integration --
    # see static/js/stripe_payment.js -- so it's off, with a graceful
    # simulated fallback, until both are configured.
    stripe_configured = bool(secret_key and publishable_key)

    if request.method == "POST":
        method = request.form.get("method")

        if method == "cash":
            svc_request.mark_paid(method="cash")
            db.session.commit()
            flash(
                f"Marked as paid by cash. Please pay ${svc_request.cost:.2f} directly to your mechanic.", "success"
            )
            return redirect(url_for("customer.request_detail", request_id=svc_request.id))

        if method == "app" and not stripe_configured:
            # No Stripe test keys configured: fall back to a simulated
            # confirmation so the flow still works out of the box. See
            # README for enabling real Stripe test-mode card payment.
            svc_request.mark_paid(method="app")
            db.session.commit()
            flash("Payment simulated successfully (no Stripe test keys configured).", "success")
            return redirect(url_for("customer.request_detail", request_id=svc_request.id))

        if method != "app":
            flash("Choose a payment method to continue.", "error")

    return render_template(
        "customer/payment_simulated.html",
        r=svc_request,
        stripe_configured=stripe_configured,
        stripe_publishable_key=publishable_key,
    )


@customer_bp.route("/requests/<int:request_id>/create-payment-intent", methods=["POST"])
@role_required("customer")
def create_payment_intent(request_id):
    """
    Called by static/js/stripe_payment.js before showing the card field.
    Creates a Stripe PaymentIntent for the exact job cost and hands back
    its client secret, which is the only thing the browser needs to collect
    and confirm the card -- the raw card number never touches this server.
    """
    svc_request = _own_request_or_404(request_id)
    if svc_request.status != "completed":
        return jsonify(error="This request isn't ready for payment yet."), 400

    secret_key, publishable_key = _stripe_keys()
    if not (secret_key and publishable_key):
        return jsonify(error="Card payment isn't configured on this server."), 400

    import stripe

    stripe.api_key = secret_key
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(svc_request.cost * 100),
            currency="usd",
            description=f"RoadRescue - {svc_request.issue_label} (request #{svc_request.id})",
            metadata={"request_id": svc_request.id},
        )
    except stripe.error.StripeError as exc:
        return jsonify(error=str(exc)), 400

    return jsonify(client_secret=intent.client_secret)


@customer_bp.route("/requests/<int:request_id>/confirm-card-payment", methods=["POST"])
@role_required("customer")
def confirm_card_payment(request_id):
    """
    Called by static/js/stripe_payment.js right after stripe.confirmCardPayment
    succeeds in the browser. Re-checks the PaymentIntent's status with Stripe
    directly (never trusts the client's word alone) before marking the
    request paid.
    """
    svc_request = _own_request_or_404(request_id)
    secret_key, _ = _stripe_keys()
    payment_intent_id = (request.get_json(silent=True) or {}).get("payment_intent_id")
    if not secret_key or not payment_intent_id:
        return jsonify(error="Missing payment confirmation."), 400

    import stripe

    stripe.api_key = secret_key
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
    except stripe.error.StripeError as exc:
        return jsonify(error=str(exc)), 400

    if intent.status != "succeeded":
        return jsonify(error="Stripe hasn't confirmed this payment yet."), 400
    if str(intent.metadata.get("request_id")) != str(svc_request.id):
        return jsonify(error="This payment doesn't match this request."), 400

    if svc_request.status == "completed":
        svc_request.mark_paid(method="app")
        db.session.commit()

    return jsonify(redirect_url=url_for("customer.request_detail", request_id=svc_request.id))


@customer_bp.route("/requests/<int:request_id>/rate", methods=["POST"])
@role_required("customer")
def rate_request(request_id):
    svc_request = _own_request_or_404(request_id)
    form = RatingForm()
    if svc_request.status != "paid":
        flash("You can only rate a request after it has been paid.", "error")
        return redirect(url_for("customer.request_detail", request_id=svc_request.id))

    if form.validate_on_submit():
        rating = Rating(request_id=svc_request.id, stars=int(form.stars.data), review_text=form.review_text.data)
        db.session.add(rating)
        svc_request.mark_rated()
        svc_request.mechanic.record_rating(int(form.stars.data))
        db.session.commit()
        flash("Thanks for rating your mechanic!", "success")
    else:
        flash("Please choose a star rating.", "error")
    return redirect(url_for("customer.request_detail", request_id=svc_request.id))


@customer_bp.route("/requests/<int:request_id>/complaint", methods=["POST"])
@role_required("customer")
def file_complaint(request_id):
    svc_request = _own_request_or_404(request_id)
    form = ComplaintForm()
    if svc_request.mechanic_id is None:
        flash("This request has no assigned mechanic to complain about.", "error")
        return redirect(url_for("customer.request_detail", request_id=svc_request.id))

    if form.validate_on_submit():
        complaint = Complaint(
            customer_id=current_user.id,
            mechanic_id=svc_request.mechanic_id,
            request_id=svc_request.id,
            text=form.text.data.strip(),
        )
        db.session.add(complaint)
        db.session.commit()
        flash("Your complaint has been submitted to our admin team.", "success")
    else:
        flash("Please describe the issue (at least 10 characters).", "error")
    return redirect(url_for("customer.request_detail", request_id=svc_request.id))


@customer_bp.route("/reviews")
@role_required("customer")
def reviews():
    """A history page listing everything this customer has rated or complained about."""
    ratings_page = request.args.get("ratings_page", 1, type=int)
    complaints_page = request.args.get("complaints_page", 1, type=int)

    ratings_pagination = (
        Rating.query.join(ServiceRequest, Rating.request_id == ServiceRequest.id)
        .filter(ServiceRequest.customer_id == current_user.id)
        .order_by(Rating.created_at.desc())
        .paginate(page=ratings_page, per_page=10, error_out=False)
    )
    complaints_pagination = (
        Complaint.query.filter_by(customer_id=current_user.id)
        .order_by(Complaint.created_at.desc())
        .paginate(page=complaints_page, per_page=10, error_out=False)
    )
    return render_template(
        "customer/reviews.html",
        ratings_pagination=ratings_pagination,
        complaints_pagination=complaints_pagination,
    )
