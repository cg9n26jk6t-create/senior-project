"""
Tests for the ServiceRequest lifecycle state machine:
pending -> accepted -> enroute -> arrived -> inprogress -> completed -> paid -> rated
"""

from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Rating


def test_pending_request_can_be_accepted(app, seeded):
    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]

    svc_request.accept(profile)

    assert svc_request.status == "accepted"
    assert svc_request.mechanic_id == profile.id


def test_already_accepted_request_cannot_be_accepted_again(app, seeded):
    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]
    svc_request.accept(profile)

    with pytest.raises(ValueError):
        svc_request.accept(profile)


def test_only_assigned_mechanic_can_advance(app, seeded):
    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]
    svc_request.accept(profile)

    other_user = seeded["admin"]  # stand-in for "some other account"
    from app.models import MechanicProfile, User

    impostor_user = User(name="Impostor", email="impostor@example.com", phone="+961 70 000 000", role="mechanic")
    impostor_user.set_password("Impostor123!")
    db.session.add(impostor_user)
    db.session.flush()
    impostor_profile = MechanicProfile(user_id=impostor_user.id, status="approved")
    db.session.add(impostor_profile)
    db.session.flush()

    with pytest.raises(ValueError):
        svc_request.advance(impostor_profile)


def test_enroute_sets_a_simulated_distance(app, seeded):
    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]
    svc_request.accept(profile)

    svc_request.advance(profile)  # accepted -> enroute

    assert svc_request.status == "enroute"
    assert svc_request.distance_km is not None
    assert svc_request.distance_km > 0


def test_enroute_auto_advances_to_arrived_once_distance_hits_zero(app, seeded):
    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]
    svc_request.accept(profile)
    svc_request.advance(profile)  # -> enroute

    # Simulate enough elapsed time that the trip must be over.
    svc_request.enroute_started_at = svc_request.enroute_started_at - timedelta(hours=1)

    svc_request.refresh_tracking()

    assert svc_request.status == "arrived"
    assert svc_request.distance_km == 0.0


def test_full_happy_path_to_rated(app, seeded):
    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]

    svc_request.accept(profile)
    assert svc_request.status == "accepted"

    svc_request.advance(profile)  # -> enroute
    assert svc_request.status == "enroute"

    svc_request.enroute_started_at = svc_request.enroute_started_at - timedelta(hours=1)
    svc_request.refresh_tracking()  # -> arrived
    assert svc_request.status == "arrived"

    svc_request.advance(profile)  # -> inprogress
    assert svc_request.status == "inprogress"

    svc_request.mark_completed(profile)
    assert svc_request.status == "completed"
    assert profile.completed_jobs == 1

    svc_request.mark_paid()
    assert svc_request.status == "paid"

    db.session.add(Rating(request_id=svc_request.id, stars=5, review_text="Great job"))
    svc_request.mark_rated()
    profile.record_rating(5)
    assert svc_request.status == "rated"
    assert profile.average_rating == 5.0


def test_cannot_pay_before_completed(app, seeded):
    svc_request = seeded["request"]  # still "pending"

    with pytest.raises(ValueError):
        svc_request.mark_paid()


def test_cannot_rate_before_paid(app, seeded):
    svc_request = seeded["request"]

    with pytest.raises(ValueError):
        svc_request.mark_rated()


def test_cannot_advance_a_pending_request(app, seeded):
    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]

    with pytest.raises(ValueError):
        svc_request.advance(profile)


def test_urgent_surcharge_is_applied(app):
    from app.models import ServiceRequest
    from app.constants import URGENT_SURCHARGE

    normal_cost = ServiceRequest.calculate_cost("flat_tire", urgent=False)
    urgent_cost = ServiceRequest.calculate_cost("flat_tire", urgent=True)

    assert urgent_cost == normal_cost + URGENT_SURCHARGE


# ---- platform commission -------------------------------------------------


def test_completing_a_job_splits_cost_between_platform_and_mechanic(app, seeded):
    from decimal import Decimal
    from app.constants import PLATFORM_COMMISSION_RATE

    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]
    svc_request.accept(profile)
    svc_request.advance(profile)  # -> enroute
    svc_request.enroute_started_at = svc_request.enroute_started_at - timedelta(hours=1)
    svc_request.refresh_tracking()  # -> arrived
    svc_request.advance(profile)  # -> inprogress

    svc_request.mark_completed(profile)

    expected_fee = round(svc_request.cost * Decimal(str(PLATFORM_COMMISSION_RATE)), 2)
    assert svc_request.platform_fee == expected_fee
    assert svc_request.mechanic_payout == svc_request.cost - expected_fee
    # The customer still owes the full cost; only the mechanic's payout is reduced.
    assert profile.earnings == svc_request.mechanic_payout


def test_mechanic_payout_is_none_before_completion(app, seeded):
    svc_request = seeded["request"]
    assert svc_request.platform_fee is None
    assert svc_request.mechanic_payout is None


# ---- appointments ---------------------------------------------------------


def test_appointment_advance_skips_enroute_and_arrived(app, seeded):
    """An appointment has the customer drop the car off, so there's no live-tracking trip to simulate."""
    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]
    svc_request.service_mode = "appointment"

    svc_request.accept(profile)
    svc_request.advance(profile)

    assert svc_request.status == "inprogress"
    assert svc_request.distance_km is None  # never went through the tracking simulation


def test_appointment_preassigned_to_one_mechanic_rejects_another(app, seeded):
    from app.models import MechanicProfile, User

    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]
    svc_request.mechanic_id = profile.id  # pre-booked with this mechanic, still "pending"

    other_user = User(name="Other Mechanic", email="other@example.com", phone="+961 71 000 111", role="mechanic")
    other_user.set_password("Other123!")
    db.session.add(other_user)
    db.session.flush()
    other_profile = MechanicProfile(user_id=other_user.id, status="approved")
    db.session.add(other_profile)
    db.session.flush()

    with pytest.raises(ValueError):
        svc_request.accept(other_profile)

    # The mechanic it was actually booked with can still accept it.
    svc_request.accept(profile)
    assert svc_request.status == "accepted"


def test_declining_a_preassigned_appointment_releases_it(app, seeded):
    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]
    svc_request.mechanic_id = profile.id

    svc_request.add_decline(profile.id)
    svc_request.release(profile)

    assert svc_request.mechanic_id is None
    assert profile.id in svc_request.decline_ids()


def test_release_does_nothing_once_accepted(app, seeded):
    """A mechanic can't back out of a job they've already accepted by declining it after the fact."""
    svc_request = seeded["request"]
    profile = seeded["mechanic_profile"]
    svc_request.accept(profile)

    svc_request.release(profile)

    assert svc_request.mechanic_id == profile.id
