"""
Populate the database with demo data: one admin, a couple of customers with
vehicles, a couple of approved mechanics (plus one pending application for
the admin-review demo), and sample requests covering several points in the
lifecycle. Safe to re-run -- it drops and recreates all tables first.

Usage:
    python seed.py
"""

import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models import User, Vehicle, MechanicProfile, Certification, ServiceRequest, Rating, Complaint
from app.constants import LEBANESE_AREA_COORDS, PLATFORM_COMMISSION_RATE

app = create_app()

# Demo accounts are treated as already-established users (not someone who
# just registered), so the dashboard greets them with "Welcome back" rather
# than the first-login-only "Welcome". See User.login_count in models.py.
ESTABLISHED_LOGIN_COUNT = 3


def make_customer(name, email, phone, password):
    user = User(name=name, email=email, phone=phone, role="customer", login_count=ESTABLISHED_LOGIN_COUNT)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def make_mechanic(name, email, phone, password, status, available=False):
    user = User(name=name, email=email, phone=phone, role="mechanic", login_count=ESTABLISHED_LOGIN_COUNT)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    profile = MechanicProfile(user_id=user.id, status=status, available=available)
    db.session.add(profile)
    db.session.flush()
    return user, profile


def make_certification(mechanic_id, label, upload_dir):
    """Writes a small placeholder document to disk and returns a Certification for it."""
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.txt"
    with open(os.path.join(upload_dir, stored_name), "w", encoding="utf-8") as handle:
        handle.write(f"Demo certification document: {label}\n")
    return Certification(mechanic_id=mechanic_id, original_filename=f"{label}.txt", stored_filename=stored_name)


def main():
    with app.app_context():
        db.drop_all()
        db.create_all()

        upload_dir = app.config["UPLOAD_FOLDER"]

        # ---- admin ----------------------------------------------------
        admin = User(
            name="Nadine Saad",
            email="admin@roadrescue.lb",
            phone="+961 1 234 567",
            role="admin",
            login_count=ESTABLISHED_LOGIN_COUNT,
        )
        admin.set_password("Admin123!")
        db.session.add(admin)

        # ---- customers --------------------------------------------------
        karim = make_customer("Karim Haddad", "karim.haddad@example.com", "+961 3 123 456", "Customer123!")
        layal = make_customer("Layal Fares", "layal.fares@example.com", "+961 71 987 654", "Customer123!")

        karim_car = Vehicle(customer_id=karim.id, make="Toyota", model="Corolla", year=2018, plate="B 123456")
        layal_suv = Vehicle(customer_id=layal.id, make="Kia", model="Sportage", year=2020, plate="M 654321")
        layal_sedan = Vehicle(customer_id=layal.id, make="Hyundai", model="Elantra", year=2015, plate="A 111222")
        db.session.add_all([karim_car, layal_suv, layal_sedan])
        db.session.flush()

        # ---- mechanics --------------------------------------------------
        georges_user, georges = make_mechanic(
            "Georges Abou Khalil", "georges.mechanic@example.com", "+961 76 555 111", "Mechanic123!",
            status="approved", available=True,
        )
        georges.current_lat, georges.current_lng = LEBANESE_AREA_COORDS["Baabda"]
        db.session.add_all([
            make_certification(georges.id, "ASE Certified Technician", upload_dir),
            make_certification(georges.id, "Toyota Factory Trained", upload_dir),
        ])

        rami_user, rami = make_mechanic(
            "Rami Nassar", "rami.mechanic@example.com", "+961 70 222 333", "Mechanic123!",
            status="approved", available=False,
        )
        rami.current_lat, rami.current_lng = LEBANESE_AREA_COORDS["Achrafieh"]
        db.session.add(make_certification(rami.id, "Bosch Certified Diesel Specialist", upload_dir))

        # A mechanic application still awaiting admin review, for the demo.
        sami_user, sami = make_mechanic(
            "Sami Khoury", "sami.mechanic@example.com", "+961 81 444 555", "Mechanic123!",
            status="pending", available=False,
        )
        db.session.add(make_certification(sami.id, "Automotive Technology Diploma - LAU", upload_dir))

        db.session.flush()

        # ---- sample requests across the lifecycle -----------------------

        # 1) Fully closed out: paid (in app) and rated.
        hamra_lat, hamra_lng = LEBANESE_AREA_COORDS["Hamra"]
        req_rated = ServiceRequest(
            customer_id=karim.id,
            vehicle_id=karim_car.id,
            mechanic_id=georges.id,
            issue_type="flat_tire",
            address="Hamra",
            urgent=False,
            status="paid",
            payment_method="app",
            preferred_payment_method="app",
            cost=ServiceRequest.calculate_cost("flat_tire", False),
            customer_lat=hamra_lat,
            customer_lng=hamra_lng,
        )
        db.session.add(req_rated)
        db.session.flush()
        db.session.add(Rating(request_id=req_rated.id, stars=5, review_text="Fast, friendly, and fixed it in minutes!"))
        req_rated.mark_rated()
        # This path jumps straight to "paid" rather than going through the
        # normal accepted -> ... -> completed flow, so it has to apply the
        # platform commission by hand the same way mark_completed() does.
        req_rated.platform_fee = round(req_rated.cost * Decimal(str(PLATFORM_COMMISSION_RATE)), 2)
        georges.completed_jobs += 1
        georges.earnings += req_rated.mechanic_payout
        georges.record_rating(5)

        # A resolved complaint tied to that same request, for the admin demo.
        db.session.add(Complaint(
            customer_id=karim.id,
            mechanic_id=georges.id,
            request_id=req_rated.id,
            text="Arrived a bit later than the ETA suggested, but did great work.",
            status="resolved",
        ))

        # 2) Completed, awaiting payment.
        achrafieh_lat, achrafieh_lng = LEBANESE_AREA_COORDS["Achrafieh"]
        req_completed = ServiceRequest(
            customer_id=layal.id,
            vehicle_id=layal_suv.id,
            mechanic_id=rami.id,
            issue_type="dead_battery",
            address="Achrafieh",
            urgent=False,
            status="inprogress",
            preferred_payment_method="cash",
            cost=ServiceRequest.calculate_cost("dead_battery", False),
            customer_lat=achrafieh_lat,
            customer_lng=achrafieh_lng,
        )
        db.session.add(req_completed)
        db.session.flush()
        req_completed.mark_completed(rami)

        # 3) Mechanic en route right now (live-tracking demo, including the map).
        baabda_lat, baabda_lng = LEBANESE_AREA_COORDS["Baabda"]
        req_enroute = ServiceRequest(
            customer_id=karim.id,
            vehicle_id=karim_car.id,
            mechanic_id=georges.id,
            issue_type="engine_trouble",
            address="Baabda",
            urgent=True,
            status="accepted",
            preferred_payment_method="app",
            cost=ServiceRequest.calculate_cost("engine_trouble", True),
            customer_lat=baabda_lat,
            customer_lng=baabda_lng,
        )
        db.session.add(req_enroute)
        db.session.flush()
        req_enroute.advance(georges)  # -> enroute, with a random simulated distance + mechanic start point

        # 4) Still waiting for a mechanic to accept.
        jounieh_lat, jounieh_lng = LEBANESE_AREA_COORDS["Jounieh"]
        req_pending = ServiceRequest(
            customer_id=layal.id,
            vehicle_id=layal_sedan.id,
            mechanic_id=None,
            issue_type="lockout",
            address="Jounieh",
            urgent=False,
            status="pending",
            preferred_payment_method="cash",
            cost=ServiceRequest.calculate_cost("lockout", False),
            customer_lat=jounieh_lat,
            customer_lng=jounieh_lng,
        )
        db.session.add(req_pending)

        # 5) "Other" issue type, with a free-text description -- still
        # waiting for a mechanic to pick it up.
        zahle_lat, zahle_lng = LEBANESE_AREA_COORDS["Zahle"]
        req_other = ServiceRequest(
            customer_id=karim.id,
            vehicle_id=karim_car.id,
            mechanic_id=None,
            issue_type="other",
            details="There's a burning rubber smell coming from the front-right wheel and a faint smoke.",
            address="Zahle",
            urgent=True,
            status="pending",
            preferred_payment_method="cash",
            cost=ServiceRequest.calculate_cost("other", True),
            customer_lat=zahle_lat,
            customer_lng=zahle_lng,
        )
        db.session.add(req_other)

        # 6) An appointment booked directly with an available mechanic,
        # awaiting their confirmation -- for the appointment-booking demo.
        req_appointment = ServiceRequest(
            customer_id=layal.id,
            vehicle_id=layal_sedan.id,
            mechanic_id=georges.id,
            issue_type="transmission_issue",
            details="Grinding noise when shifting from first to second gear.",
            address="Baabda",
            urgent=False,
            status="pending",
            service_mode="appointment",
            appointment_date=date.today() + timedelta(days=5),
            appointment_time_of_day="morning",
            preferred_payment_method="app",
            cost=ServiceRequest.calculate_cost("transmission_issue", False),
            customer_lat=jounieh_lat,
            customer_lng=jounieh_lng,
        )
        db.session.add(req_appointment)

        db.session.commit()

        print("Seed data created:")
        print("  Admin:      admin@roadrescue.lb / Admin123!")
        print("  Customer:   karim.haddad@example.com / Customer123!")
        print("  Customer:   layal.fares@example.com / Customer123!")
        print("  Mechanic:   georges.mechanic@example.com / Mechanic123! (approved, available)")
        print("  Mechanic:   rami.mechanic@example.com / Mechanic123! (approved, offline)")
        print("  Mechanic:   sami.mechanic@example.com / Mechanic123! (pending approval)")


if __name__ == "__main__":
    main()
