"""
Role-based access control tests: a logged-in customer must not be able to
reach mechanic- or admin-only routes (and vice versa), and protected routes
must require login at all.
"""

from tests.conftest import login


def test_anonymous_user_is_redirected_to_login(client, seeded):
    response = client.get("/customer/dashboard")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_customer_cannot_access_mechanic_dashboard(client, seeded):
    login(client, "karim@example.com", "Customer123!")

    response = client.get("/mechanic/dashboard")

    assert response.status_code == 403


def test_customer_cannot_access_admin_dashboard(client, seeded):
    login(client, "karim@example.com", "Customer123!")

    response = client.get("/admin/dashboard")

    assert response.status_code == 403


def test_mechanic_cannot_access_customer_dashboard(client, seeded):
    login(client, "georges@example.com", "Mechanic123!")

    response = client.get("/customer/dashboard")

    assert response.status_code == 403


def test_mechanic_cannot_access_admin_mechanics_list(client, seeded):
    login(client, "georges@example.com", "Mechanic123!")

    response = client.get("/admin/mechanics")

    assert response.status_code == 403


def test_customer_cannot_approve_mechanics(client, seeded):
    login(client, "karim@example.com", "Customer123!")

    response = client.post(f"/admin/mechanics/{seeded['mechanic_profile'].id}/approve")

    assert response.status_code == 403


def test_customer_cannot_access_another_customers_request(client, seeded, app):
    from app.extensions import db
    from app.models import User

    other_customer = User(name="Layal Fares", email="layal@example.com", phone="+961 71 987 654", role="customer")
    other_customer.set_password("Customer123!")
    db.session.add(other_customer)
    db.session.commit()

    login(client, "layal@example.com", "Customer123!")

    response = client.get(f"/customer/requests/{seeded['request'].id}")

    assert response.status_code == 403


def test_admin_can_reach_admin_dashboard(client, seeded):
    login(client, "admin@roadrescue.lb", "Admin123!")

    response = client.get("/admin/dashboard")

    assert response.status_code == 200


def test_customer_can_reach_own_dashboard(client, seeded):
    login(client, "karim@example.com", "Customer123!")

    response = client.get("/customer/dashboard")

    assert response.status_code == 200
