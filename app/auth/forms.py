from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Regexp

from ..constants import LEBANON_PHONE_REGEX

PHONE_MESSAGE = "Enter a Lebanese number in the format +961 71 234 567."


class RegisterForm(FlaskForm):
    role = SelectField(
        "I am registering as a",
        choices=[("customer", "Customer looking for help"), ("mechanic", "Mechanic offering services")],
        validators=[DataRequired()],
    )
    name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField(
        "Phone number",
        validators=[DataRequired(), Regexp(LEBANON_PHONE_REGEX, message=PHONE_MESSAGE)],
        render_kw={"placeholder": "+961 71 234 567"},
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, message="Use at least 8 characters.")])
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Keep me logged in")
