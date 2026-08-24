from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    IntegerField,
    SelectField,
    BooleanField,
    TextAreaField,
    RadioField,
    HiddenField,
    DateField,
)
from wtforms.validators import DataRequired, Email, Length, Regexp, NumberRange, Optional

from ..constants import (
    LEBANON_PHONE_REGEX,
    ISSUE_TYPES,
    URGENT_SURCHARGE,
    SERVICE_MODES,
    APPOINTMENT_TIME_SLOTS,
    PAYMENT_METHOD_CHOICES,
)

PHONE_MESSAGE = "Enter a Lebanese number in the format +961 71 234 567."


class ProfileForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField("Phone number", validators=[DataRequired(), Regexp(LEBANON_PHONE_REGEX, message=PHONE_MESSAGE)])
    new_password = PasswordField(
        "New password (leave blank to keep current)", validators=[Optional(), Length(min=8, message="Use at least 8 characters.")]
    )


class VehicleForm(FlaskForm):
    make = StringField("Make", validators=[DataRequired(), Length(max=60)])
    model = StringField("Model", validators=[DataRequired(), Length(max=60)])
    year = IntegerField("Year", validators=[DataRequired(), NumberRange(min=1970, max=date.today().year + 1)])
    plate = StringField("License plate", validators=[DataRequired(), Length(max=20)])


class ServiceRequestForm(FlaskForm):
    vehicle_id = SelectField("Vehicle", coerce=int, validators=[DataRequired()])
    issue_type = SelectField(
        "What's the issue?",
        choices=[(key, f"{label} (${price})") for key, (label, price) in ISSUE_TYPES.items()],
        validators=[DataRequired()],
    )
    # Optional for most issue types; the route enforces it's filled in when
    # issue_type == "other", since there's no category to fall back on.
    details = TextAreaField(
        "Anything else you can tell us about the problem?", validators=[Optional(), Length(max=1000)]
    )
    address = StringField("Your location", validators=[DataRequired(), Length(max=200)])
    # Populated by the map picker in static/js/location_picker.js when the
    # customer drops a pin. Optional -- typing an address alone still works.
    latitude = HiddenField(validators=[Optional()])
    longitude = HiddenField(validators=[Optional()])
    urgent = BooleanField(f"This is urgent (+${URGENT_SURCHARGE})")

    service_mode = SelectField(
        "How would you like this handled?", choices=list(SERVICE_MODES.items()), validators=[DataRequired()]
    )
    # The next three are only required when service_mode == "appointment";
    # enforced in the route rather than here since WTForms validators can't
    # easily see a sibling field's value at construction time.
    appointment_date = DateField("Drop-off date", validators=[Optional()])
    appointment_time_of_day = SelectField(
        "Preferred time",
        choices=[("", "Select a time")] + APPOINTMENT_TIME_SLOTS,
        validators=[Optional()],
    )
    appointment_mechanic_id = SelectField("Mechanic", coerce=int, validators=[Optional()])

    preferred_payment_method = RadioField(
        "How do you plan to pay?", choices=PAYMENT_METHOD_CHOICES, default="app", validators=[DataRequired()]
    )


class RatingForm(FlaskForm):
    stars = RadioField("Rating", choices=[(str(n), str(n)) for n in range(1, 6)], validators=[DataRequired()])
    review_text = TextAreaField("Review (optional)", validators=[Optional(), Length(max=1000)])


class ComplaintForm(FlaskForm):
    text = TextAreaField("Describe the issue", validators=[DataRequired(), Length(min=10, max=1000)])
