"""
SQLAlchemy models for RoadRescue.

One User table covers all three roles (customer / mechanic / admin);
mechanic-only data (certifications, availability, rating, earnings) lives
in a separate MechanicProfile table linked one-to-one, so a customer row
never carries a pile of empty mechanic columns.
"""

import math
import random
from datetime import datetime
from decimal import Decimal

from flask import current_app
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db
from .constants import (
    ISSUE_TYPES,
    URGENT_SURCHARGE,
    MECHANIC_ADVANCEABLE,
    APPOINTMENT_ADVANCEABLE,
    DISPLAY_SPEED_KMH,
    DEMO_ACCELERATION,
    PLATFORM_COMMISSION_RATE,
)


def utcnow():
    # Naive UTC on purpose: SQLite drops tzinfo on round-trip, so a
    # timezone-aware value here would fail to compare against a value just
    # loaded back from the database (see refresh_tracking below).
    return datetime.utcnow()


def distance_between_km(lat1, lng1, lat2, lng2):
    """
    Straight-line distance between two points, in km. Uses a flat-earth
    approximation (1 degree latitude = 111km) rather than full geodesic
    math -- Lebanon's small size makes the error negligible, and this is
    only used to rank/display nearby jobs, not to route anyone. Named
    distinctly from ServiceRequest.distance_km (the live-tracking column)
    to avoid confusing the two.
    """
    km_per_degree_lng = 111.0 * math.cos(math.radians((lat1 + lat2) / 2))
    dlat_km = (lat2 - lat1) * 111.0
    dlng_km = (lng2 - lng1) * km_per_degree_lng
    return math.hypot(dlat_km, dlng_km)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # customer | mechanic | admin
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    # Incremented on every successful login (see auth/routes.py). A value of
    # 1 means "this is the session right after their very first login" --
    # used to show "Welcome" instead of "Welcome back" just that one time.
    login_count = db.Column(db.Integer, nullable=False, default=0)

    vehicles = db.relationship("Vehicle", backref="owner", cascade="all, delete-orphan")
    mechanic_profile = db.relationship(
        "MechanicProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def generate_reset_token(self):
        """
        A signed, stateless token encoding this user's email -- no database
        column needed to track it, and it self-expires (see
        verify_reset_token) without any cleanup job.
        """
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        return serializer.dumps(self.email, salt="password-reset")

    @staticmethod
    def verify_reset_token(token, max_age):
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        try:
            email = serializer.loads(token, salt="password-reset", max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        return User.query.filter_by(email=email).first()

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    make = db.Column(db.String(60), nullable=False)
    model = db.Column(db.String(60), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    plate = db.Column(db.String(20), nullable=False)

    requests = db.relationship("ServiceRequest", backref="vehicle")

    @property
    def label(self):
        return f"{self.year} {self.make} {self.model} ({self.plate})"


class MechanicProfile(db.Model):
    __tablename__ = "mechanic_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    # unregistered -> pending -> approved (or suspended by an admin)
    status = db.Column(db.String(20), nullable=False, default="unregistered")
    available = db.Column(db.Boolean, nullable=False, default=False)

    # Set by the mechanic themselves (see mechanic.update_location). Used to
    # sort incoming on-demand requests by distance and to let a customer
    # booking an appointment see who is actually nearby.
    current_lat = db.Column(db.Float, nullable=True)
    current_lng = db.Column(db.Float, nullable=True)

    rating_total = db.Column(db.Float, nullable=False, default=0.0)  # sum of stars, used to derive the average
    rating_count = db.Column(db.Integer, nullable=False, default=0)
    completed_jobs = db.Column(db.Integer, nullable=False, default=0)
    earnings = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    certifications = db.relationship(
        "Certification", backref="mechanic", cascade="all, delete-orphan", order_by="Certification.created_at"
    )
    jobs = db.relationship("ServiceRequest", backref="mechanic")

    @property
    def average_rating(self):
        if self.rating_count == 0:
            return None
        return round(self.rating_total / self.rating_count, 1)

    def record_rating(self, stars):
        self.rating_total += stars
        self.rating_count += 1


class Certification(db.Model):
    """
    A certification document a mechanic uploaded for admin review.
    `stored_filename` is a random name on disk (see UPLOAD_FOLDER) so
    uploads never collide or leak the original path; `original_filename`
    is what gets shown/downloaded.
    """

    __tablename__ = "certifications"

    id = db.Column(db.Integer, primary_key=True)
    mechanic_id = db.Column(db.Integer, db.ForeignKey("mechanic_profiles.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class ServiceRequest(db.Model):
    __tablename__ = "service_requests"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    mechanic_id = db.Column(db.Integer, db.ForeignKey("mechanic_profiles.id"), nullable=True)

    issue_type = db.Column(db.String(30), nullable=False)
    details = db.Column(db.Text, nullable=True)  # free-text notes; required when issue_type == "other"
    address = db.Column(db.String(200), nullable=False)
    urgent = db.Column(db.Boolean, nullable=False, default=False)

    # "on_demand" (mechanic travels to the customer, the original flow) or
    # "appointment" (customer drops the car off at the mechanic's workshop
    # on a chosen date/time -- for problems that aren't fixable roadside).
    service_mode = db.Column(db.String(20), nullable=False, default="on_demand")
    appointment_date = db.Column(db.Date, nullable=True)
    appointment_time_of_day = db.Column(db.String(20), nullable=True)

    # How the customer said they intend to pay when they made the request.
    # Just a stated preference -- the actual payment step (payment_method,
    # below) still lets them pick either option when the job is done.
    preferred_payment_method = db.Column(db.String(10), nullable=True)

    # Optional pin dropped on the map when requesting help. Null if the
    # customer only typed a text address (map picking is not required).
    customer_lat = db.Column(db.Float, nullable=True)
    customer_lng = db.Column(db.Float, nullable=True)

    # A simulated starting point for the mechanic, chosen once "enroute"
    # begins, exactly initial_distance_km away from the customer pin at a
    # random bearing -- see advance() below. Used to animate a mechanic
    # marker moving toward the customer on the live-tracking map.
    mechanic_start_lat = db.Column(db.Float, nullable=True)
    mechanic_start_lng = db.Column(db.Float, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="pending")
    cost = db.Column(db.Numeric(10, 2), nullable=False)

    # RoadRescue's commission on this job, in dollars, fixed at completion
    # time (see mark_completed). Null until then. The customer still pays
    # the full `cost`; this is only what the platform keeps out of it --
    # the mechanic is credited cost - platform_fee.
    platform_fee = db.Column(db.Numeric(10, 2), nullable=True)

    # Set once the customer chooses how to pay: "app" (Stripe/simulated) or
    # "cash" (paid directly to the mechanic). Null until then.
    payment_method = db.Column(db.String(10), nullable=True)

    # Live-tracking simulation for the "enroute" phase.
    distance_km = db.Column(db.Float, nullable=True)          # current remaining distance
    initial_distance_km = db.Column(db.Float, nullable=True)  # distance when "enroute" started
    enroute_started_at = db.Column(db.DateTime, nullable=True)

    # Mechanics who declined this request should not see it offered again,
    # but it stays open for every other available mechanic.
    declined_by = db.Column(db.String(200), nullable=False, default="")

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    customer = db.relationship("User", foreign_keys=[customer_id])
    rating = db.relationship("Rating", backref="request", uselist=False, cascade="all, delete-orphan")
    complaints = db.relationship("Complaint", backref="request", cascade="all, delete-orphan")

    # ---- pricing -------------------------------------------------------

    @staticmethod
    def calculate_cost(issue_type, urgent):
        _, base_price = ISSUE_TYPES[issue_type]
        return base_price + (URGENT_SURCHARGE if urgent else 0)

    @property
    def issue_label(self):
        return ISSUE_TYPES[self.issue_type][0]

    # ---- declines --------------------------------------------------

    def decline_ids(self):
        return [int(x) for x in self.declined_by.split(",") if x]

    def add_decline(self, mechanic_id):
        ids = set(self.decline_ids())
        ids.add(mechanic_id)
        self.declined_by = ",".join(str(i) for i in ids)

    # ---- state machine ---------------------------------------------

    def cancel(self):
        """
        A customer can only back out before a mechanic has committed to the
        job -- once accepted, the mechanic may already be on their way or
        have set aside the appointment slot, so cancellation stops here.
        """
        if self.status != "pending":
            raise ValueError("Only a pending request can be cancelled.")
        self.status = "cancelled"

    def accept(self, mechanic_profile):
        if self.status != "pending":
            raise ValueError("Only a pending request can be accepted.")
        if self.mechanic_id is not None and self.mechanic_id != mechanic_profile.id:
            raise ValueError("This appointment was booked with a different mechanic.")
        self.mechanic_id = mechanic_profile.id
        self.status = "accepted"

    def release(self, mechanic_profile):
        """
        A mechanic declining an appointment that was booked specifically with
        them (mechanic_id was pre-set at booking time) frees it up for any
        other available mechanic, rather than leaving it stuck.
        """
        if self.mechanic_id == mechanic_profile.id and self.status == "pending":
            self.mechanic_id = None

    def advance(self, mechanic_profile):
        """Move the job forward one step, e.g. accepted -> enroute."""
        if self.mechanic_id != mechanic_profile.id:
            raise ValueError("Only the assigned mechanic can update this job.")
        mapping = APPOINTMENT_ADVANCEABLE if self.service_mode == "appointment" else MECHANIC_ADVANCEABLE
        next_status = mapping.get(self.status)
        if next_status is None:
            raise ValueError(f"A request in status '{self.status}' cannot be advanced manually.")
        self.status = next_status
        if next_status == "enroute":
            self.initial_distance_km = round(random.uniform(2.0, 15.0), 1)
            self.distance_km = self.initial_distance_km
            self.enroute_started_at = utcnow()
            if self.customer_lat is not None and self.customer_lng is not None:
                self._place_mechanic_start()

    def _place_mechanic_start(self):
        """
        Pick a random point exactly initial_distance_km from the customer's
        pin, for the mechanic marker to animate in from. Uses a flat-earth
        approximation (fine at Lebanon's scale, ~1 degree latitude = 111km)
        rather than full geodesic math -- precision doesn't matter for a
        simulated position.
        """
        bearing = random.uniform(0, 2 * math.pi)
        km_per_degree_lat = 111.0
        km_per_degree_lng = 111.0 * math.cos(math.radians(self.customer_lat))
        self.mechanic_start_lat = self.customer_lat + (self.initial_distance_km * math.cos(bearing)) / km_per_degree_lat
        self.mechanic_start_lng = self.customer_lng + (self.initial_distance_km * math.sin(bearing)) / km_per_degree_lng

    @property
    def mechanic_position(self):
        """Current (lat, lng) of the simulated mechanic marker, or None if no map pin was set."""
        if self.mechanic_start_lat is None or self.distance_km is None or not self.initial_distance_km:
            return None
        fraction_traveled = 1 - (self.distance_km / self.initial_distance_km)
        lat = self.mechanic_start_lat + (self.customer_lat - self.mechanic_start_lat) * fraction_traveled
        lng = self.mechanic_start_lng + (self.customer_lng - self.mechanic_start_lng) * fraction_traveled
        return lat, lng

    def refresh_tracking(self):
        """
        Recompute the simulated remaining distance for an "enroute" job.
        Auto-advances to "arrived" once the distance reaches zero.
        Safe to call repeatedly (e.g. on every polling request).
        """
        if self.status != "enroute" or self.enroute_started_at is None:
            return
        elapsed_seconds = (utcnow() - self.enroute_started_at).total_seconds()
        km_per_second = (DISPLAY_SPEED_KMH / 3600) * DEMO_ACCELERATION
        remaining = self.initial_distance_km - elapsed_seconds * km_per_second
        if remaining <= 0:
            self.distance_km = 0.0
            self.status = "arrived"
        else:
            self.distance_km = round(remaining, 2)

    @property
    def eta_minutes(self):
        """Realistic ETA (not accelerated) shown to the customer."""
        if self.distance_km is None:
            return None
        return round(self.distance_km / DISPLAY_SPEED_KMH * 60, 1)

    def mark_completed(self, mechanic_profile):
        if self.mechanic_id != mechanic_profile.id:
            raise ValueError("Only the assigned mechanic can complete this job.")
        if self.status != "inprogress":
            raise ValueError("Only a job that is in progress can be completed.")
        self.status = "completed"
        # self.cost is a Decimal (Numeric column); PLATFORM_COMMISSION_RATE
        # is a plain float constant, and Decimal * float raises TypeError,
        # so it has to come in via str() rather than multiplying directly.
        self.platform_fee = round(self.cost * Decimal(str(PLATFORM_COMMISSION_RATE)), 2)
        mechanic_profile.completed_jobs += 1
        mechanic_profile.earnings = (mechanic_profile.earnings or 0) + self.mechanic_payout

    @property
    def mechanic_payout(self):
        """What the mechanic actually gets for this job -- the customer pays `cost` in full."""
        if self.platform_fee is None:
            return None
        return self.cost - self.platform_fee

    def mark_paid(self, method="app"):
        if self.status != "completed":
            raise ValueError("Only a completed request can be paid for.")
        if method not in ("app", "cash"):
            raise ValueError("Payment method must be 'app' or 'cash'.")
        self.status = "paid"
        self.payment_method = method

    def mark_rated(self):
        if self.status != "paid":
            raise ValueError("Only a paid request can be rated.")
        self.status = "rated"


class Rating(db.Model):
    __tablename__ = "ratings"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("service_requests.id"), unique=True, nullable=False)
    stars = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mechanic_id = db.Column(db.Integer, db.ForeignKey("mechanic_profiles.id"), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey("service_requests.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")  # open | resolved
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    customer = db.relationship("User")
