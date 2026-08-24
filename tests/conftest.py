import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User, Vehicle, MechanicProfile, ServiceRequest


@pytest.fixture()
def app():
    application = create_app(TestingConfig)
    with application.app_context():
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def seeded(app):
    """Create one customer, one approved mechanic, a vehicle, and a pending request."""
    customer = User(name="Karim Haddad", email="karim@example.com", phone="+961 3 123 456", role="customer")
    customer.set_password("Customer123!")
    db.session.add(customer)

    mechanic_user = User(name="Georges Abou Khalil", email="georges@example.com", phone="+961 76 555 111", role="mechanic")
    mechanic_user.set_password("Mechanic123!")
    db.session.add(mechanic_user)

    admin = User(name="Nadine Saad", email="admin@roadrescue.lb", phone="+961 1 234 567", role="admin")
    admin.set_password("Admin123!")
    db.session.add(admin)

    db.session.flush()

    profile = MechanicProfile(user_id=mechanic_user.id, status="approved", available=True)
    db.session.add(profile)
    db.session.flush()

    vehicle = Vehicle(customer_id=customer.id, make="Toyota", model="Corolla", year=2020, plate="B 123456")
    db.session.add(vehicle)
    db.session.flush()

    svc_request = ServiceRequest(
        customer_id=customer.id,
        vehicle_id=vehicle.id,
        issue_type="flat_tire",
        address="Hamra",
        urgent=False,
        status="pending",
        cost=ServiceRequest.calculate_cost("flat_tire", False),
    )
    db.session.add(svc_request)
    db.session.commit()

    return {
        "customer": customer,
        "mechanic_user": mechanic_user,
        "mechanic_profile": profile,
        "admin": admin,
        "vehicle": vehicle,
        "request": svc_request,
    }


def login(client, email, password):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)
