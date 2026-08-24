import re

from app.extensions import db
from app.models import User

from .conftest import login


def test_generate_and_verify_reset_token_round_trip(app, seeded):
    customer = seeded["customer"]
    token = customer.generate_reset_token()
    found = User.verify_reset_token(token, max_age=3600)
    assert found is not None
    assert found.id == customer.id


def test_verify_reset_token_rejects_garbage(app):
    assert User.verify_reset_token("not-a-real-token", max_age=3600) is None


def test_verify_reset_token_rejects_expired_token(app, seeded):
    customer = seeded["customer"]
    token = customer.generate_reset_token()
    # A negative max_age means any elapsed time at all counts as "too old".
    assert User.verify_reset_token(token, max_age=-1) is None


def test_forgot_password_shows_generic_message_for_unknown_email(client):
    response = client.post("/auth/forgot-password", data={"email": "nobody@example.com"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"If that email is registered" in response.data


def test_forgot_password_dev_mode_surfaces_reset_link_when_no_mail_server(client, seeded):
    response = client.post("/auth/forgot-password", data={"email": "karim@example.com"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"reset link directly (dev mode)" in response.data


def test_full_reset_flow_lets_user_log_in_with_new_password(client, seeded):
    response = client.post("/auth/forgot-password", data={"email": "karim@example.com"}, follow_redirects=True)
    match = re.search(rb"(/auth/reset-password/[\w\-\.]+)", response.data)
    assert match is not None
    reset_path = match.group(1).decode()

    response = client.post(
        reset_path,
        data={"password": "NewPassword123!", "confirm_password": "NewPassword123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"password has been updated" in response.data

    old_login = login(client, "karim@example.com", "Customer123!")
    assert b"Incorrect email or password" in old_login.data

    new_login = login(client, "karim@example.com", "NewPassword123!")
    assert b"Incorrect email or password" not in new_login.data


def test_reset_password_rejects_invalid_token(client):
    response = client.get("/auth/reset-password/bogus-token", follow_redirects=True)
    assert response.status_code == 200
    assert b"invalid or has expired" in response.data


def test_reset_password_rejects_mismatched_confirmation(client, seeded):
    customer = seeded["customer"]
    token = customer.generate_reset_token()
    response = client.post(
        f"/auth/reset-password/{token}",
        data={"password": "NewPassword123!", "confirm_password": "Different123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    still_works = login(client, "karim@example.com", "Customer123!")
    assert b"Incorrect email or password" not in still_works.data
