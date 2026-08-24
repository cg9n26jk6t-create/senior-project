"""
Route-level tests for the newer request features: the "Other" issue type
requiring a description, appointment booking's extra requirements, and
sorting a mechanic's incoming on-demand requests by distance.
"""

from app.extensions import db
from app.models import ServiceRequest, MechanicProfile, User

from tests.conftest import login


def _base_request_form(seeded, **overrides):
    form = {
        "vehicle_id": str(seeded["vehicle"].id),
        "issue_type": "flat_tire",
        "details": "",
        "address": "Hamra",
        "latitude": "",
        "longitude": "",
        "urgent": "",
        "service_mode": "on_demand",
        "appointment_date": "",
        "appointment_time_of_day": "",
        "appointment_mechanic_id": "0",
        "preferred_payment_method": "app",
    }
    form.update(overrides)
    return form


def test_other_issue_type_requires_details(client, seeded):
    login(client, "karim@example.com", "Customer123!")

    response = client.post(
        "/customer/requests/new",
        data=_base_request_form(seeded, issue_type="other", details=""),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"describe the problem" in response.data.lower()
    assert ServiceRequest.query.filter_by(issue_type="other").count() == 0


def test_other_issue_type_succeeds_with_details(client, seeded):
    login(client, "karim@example.com", "Customer123!")

    response = client.post(
        "/customer/requests/new",
        data=_base_request_form(seeded, issue_type="other", details="Strange clicking noise from the engine."),
        follow_redirects=True,
    )

    assert response.status_code == 200
    created = ServiceRequest.query.filter_by(issue_type="other").first()
    assert created is not None
    assert created.details == "Strange clicking noise from the engine."


def test_appointment_requires_date_time_and_mechanic(client, seeded):
    login(client, "karim@example.com", "Customer123!")

    response = client.post(
        "/customer/requests/new",
        data=_base_request_form(seeded, service_mode="appointment"),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert ServiceRequest.query.filter_by(service_mode="appointment").count() == 0


def test_appointment_booking_preassigns_the_chosen_mechanic(client, seeded):
    login(client, "karim@example.com", "Customer123!")
    mechanic_profile = seeded["mechanic_profile"]

    response = client.post(
        "/customer/requests/new",
        data=_base_request_form(
            seeded,
            service_mode="appointment",
            appointment_date="2027-01-15",
            appointment_time_of_day="morning",
            appointment_mechanic_id=str(mechanic_profile.id),
        ),
        follow_redirects=True,
    )

    assert response.status_code == 200
    created = ServiceRequest.query.filter_by(service_mode="appointment").first()
    assert created is not None
    assert created.mechanic_id == mechanic_profile.id
    assert created.status == "pending"  # still needs the mechanic to accept


def test_customer_can_cancel_own_pending_request(client, seeded):
    login(client, "karim@example.com", "Customer123!")

    response = client.post(f"/customer/requests/{seeded['request'].id}/cancel", follow_redirects=True)

    assert response.status_code == 200
    assert seeded["request"].status == "cancelled"


def test_customer_cannot_cancel_another_customers_request(client, seeded, app):
    other_customer = User(name="Layal Fares", email="layal@example.com", phone="+961 71 987 654", role="customer")
    other_customer.set_password("Customer123!")
    db.session.add(other_customer)
    db.session.commit()

    login(client, "layal@example.com", "Customer123!")
    response = client.post(f"/customer/requests/{seeded['request'].id}/cancel")

    assert response.status_code == 403
    assert seeded["request"].status == "pending"


def test_incoming_requests_sorted_nearest_first(client, app, seeded):
    """A mechanic with a location set should see closer on-demand jobs first."""
    profile = seeded["mechanic_profile"]
    profile.current_lat, profile.current_lng = 33.8938, 35.5018  # Beirut

    # Reuse the seeded pending request as the "far" one, and add a "near" one.
    seeded["request"].customer_lat, seeded["request"].customer_lng = 34.4367, 35.8497  # Tripoli (far)
    near_request = ServiceRequest(
        customer_id=seeded["customer"].id,
        vehicle_id=seeded["vehicle"].id,
        issue_type="lockout",
        address="Achrafieh",
        urgent=False,
        status="pending",
        cost=ServiceRequest.calculate_cost("lockout", False),
        customer_lat=33.8886,
        customer_lng=35.5165,  # Achrafieh (near)
    )
    db.session.add(near_request)
    db.session.commit()

    login(client, "georges@example.com", "Mechanic123!")
    response = client.get("/mechanic/requests")

    page = response.data.decode()
    # The nearer request's address should appear before the farther one's.
    assert page.index("Achrafieh") < page.index("Hamra")
