"""
Tests for the search/filter controls added to the admin and mechanic list
pages -- not just that the pages load, but that the filters actually narrow
the results and that pagination links preserve the active filter.
"""

from app.extensions import db
from app.models import User, MechanicProfile, ServiceRequest

from tests.conftest import login


def test_admin_mechanics_filter_by_status(client, seeded):
    pending_user = User(name="Pending Pete", email="pete@example.com", phone="+961 3 111 222", role="mechanic")
    pending_user.set_password("Pete123!")
    db.session.add(pending_user)
    db.session.flush()
    db.session.add(MechanicProfile(user_id=pending_user.id, status="pending"))
    db.session.commit()

    login(client, "admin@roadrescue.lb", "Admin123!")

    response = client.get("/admin/mechanics?status=pending")
    page = response.data.decode()

    assert "Pending Pete" in page
    assert "Georges" not in page  # seeded's approved mechanic is named "Georges Abou Khalil"


def test_admin_customers_search_by_name(client, seeded):
    other_customer = User(name="Layal Fares", email="layal@example.com", phone="+961 71 987 654", role="customer")
    other_customer.set_password("Customer123!")
    db.session.add(other_customer)
    db.session.commit()

    login(client, "admin@roadrescue.lb", "Admin123!")

    response = client.get("/admin/customers?q=Layal")
    page = response.data.decode()

    assert "Layal Fares" in page
    assert "Karim Haddad" not in page


def test_mechanic_job_history_filter_by_status(client, seeded):
    profile = seeded["mechanic_profile"]
    cancelled_request = ServiceRequest(
        customer_id=seeded["customer"].id,
        vehicle_id=seeded["vehicle"].id,
        mechanic_id=profile.id,
        issue_type="lockout",
        address="Achrafieh",
        urgent=False,
        status="cancelled",
        cost=ServiceRequest.calculate_cost("lockout", False),
    )
    db.session.add(cancelled_request)
    db.session.commit()

    login(client, "georges@example.com", "Mechanic123!")

    response = client.get("/mechanic/jobs?status=cancelled")
    page = response.data.decode()

    assert "Lockout" in page
    assert "Flat tire" not in page  # seeded's other job for this mechanic, a different issue type


def test_pagination_link_preserves_active_filter(client, seeded):
    """Filtering must survive clicking to page 2, not silently drop back to the unfiltered list."""
    for i in range(15):
        user = User(
            name=f"Approved Mechanic {i}", email=f"approved{i}@example.com", phone="+961 3 000 000", role="mechanic"
        )
        user.set_password("Temp123!")
        db.session.add(user)
        db.session.flush()
        db.session.add(MechanicProfile(user_id=user.id, status="approved"))
    db.session.commit()

    login(client, "admin@roadrescue.lb", "Admin123!")
    response = client.get("/admin/mechanics?status=approved")

    assert b"status=approved" in response.data
