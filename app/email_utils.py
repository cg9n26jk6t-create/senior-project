"""
Minimal outbound email support, used only for password-reset links.

Deliberately built on the standard library's smtplib rather than adding a
dependency like Flask-Mail: this app sends exactly one kind of email, so a
small helper is easier to follow than a general-purpose mailing library.
"""

import smtplib
from email.mime.text import MIMEText

from flask import current_app


def send_email(to_address, subject, body):
    """
    Sends a plain-text email via the SMTP server in config, if one is set.
    Returns True if a send was attempted and did not raise, False if no
    mail server is configured at all (the caller should have a fallback for
    that case -- see auth.forgot_password). Raises on an actual send
    failure (bad credentials, unreachable server, etc.) so the caller can
    decide how to react rather than silently losing the email.
    """
    server_host = current_app.config.get("MAIL_SERVER")
    if not server_host:
        return False

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
    message["To"] = to_address

    with smtplib.SMTP(server_host, current_app.config["MAIL_PORT"], timeout=10) as smtp:
        if current_app.config.get("MAIL_USE_TLS"):
            smtp.starttls()
        username = current_app.config.get("MAIL_USERNAME")
        password = current_app.config.get("MAIL_PASSWORD")
        if username and password:
            smtp.login(username, password)
        smtp.sendmail(current_app.config["MAIL_DEFAULT_SENDER"], [to_address], message.as_string())

    return True
