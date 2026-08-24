"""
Tests for the payment routes: cash, the no-Stripe-configured simulated
fallback, and that the card-payment endpoints fail gracefully (rather than
crashing) when Stripe test keys aren't set -- which is the only path
testable without a real Stripe account.
"""

from datetime import timedelta

from app.extensions import db

from tests.conftest import login


def _advance_to_completed(svc_request, profile):
    svc_request.accept(profile)
    svc_request.advance(profile)  # -> enroute
    svc_request.enroute_started_at = svc_request.enroute_started_at - timedelta(hours=1)
    svc_request.refresh_tracking()  # -> arrived
    svc_request.advance(profile)  # -> inprogress
    svc_request.mark_completed(profile)
    db.session.commit()


def test_pay_with_cash_marks_request_paid(client, seeded):
    _advance_to_completed(seeded["request"], seeded["mechanic_profile"])
    login(client, "karim@example.com", "Customer123!")

    response = client.post(
        f"/customer/requests/{seeded['request'].id}/pay", data={"method": "cash"}, follow_redirects=True
    )

    assert response.status_code == 200
    assert seeded["request"].status == "paid"
    assert seeded["request"].payment_method == "cash"


def test_pay_in_app_without_stripe_configured_simulates_payment(client, seeded):
    """TestingConfig has no Stripe keys, so this exercises the honest fallback path."""
    _advance_to_completed(seeded["request"], seeded["mechanic_profile"])
    login(client, "karim@example.com", "Customer123!")

    response = client.post(
        f"/customer/requests/{seeded['request'].id}/pay", data={"method": "app"}, follow_redirects=True
    )

    assert response.status_code == 200
    assert seeded["request"].status == "paid"
    assert seeded["request"].payment_method == "app"


def test_cannot_pay_a_request_that_is_not_completed(client, seeded):
    """seeded['request'] is still "pending" -- paying it must fail cleanly, not 500."""
    login(client, "karim@example.com", "Customer123!")

    response = client.post(
        f"/customer/requests/{seeded['request'].id}/pay", data={"method": "cash"}, follow_redirects=True
    )

    assert response.status_code == 200
    assert seeded["request"].status == "pending"
    assert b"isn&#39;t ready for payment" in response.data or b"isn't ready for payment" in response.data


def test_create_payment_intent_without_stripe_configured_returns_error_json(client, seeded):
    _advance_to_completed(seeded["request"], seeded["mechanic_profile"])
    login(client, "karim@example.com", "Customer123!")

    response = client.post(f"/customer/requests/{seeded['request'].id}/create-payment-intent")

    assert response.status_code == 400
    assert "error" in response.get_json()
    assert seeded["request"].status == "completed"  # unchanged


def test_confirm_card_payment_without_payment_intent_id_returns_error_json(client, seeded):
    _advance_to_completed(seeded["request"], seeded["mechanic_profile"])
    login(client, "karim@example.com", "Customer123!")

    response = client.post(
        f"/customer/requests/{seeded['request'].id}/confirm-card-payment",
        json={},
    )

    assert response.status_code == 400
    assert "error" in response.get_json()
    assert seeded["request"].status == "completed"  # unchanged


def test_customer_cannot_pay_for_another_customers_request(client, seeded, app):
    from app.models import User

    other_customer = User(name="Layal Fares", email="layal@example.com", phone="+961 71 987 654", role="customer")
    other_customer.set_password("Customer123!")
    db.session.add(other_customer)
    db.session.commit()

    _advance_to_completed(seeded["request"], seeded["mechanic_profile"])
    login(client, "layal@example.com", "Customer123!")

    response = client.post(f"/customer/requests/{seeded['request'].id}/pay", data={"method": "cash"})

    assert response.status_code == 403
