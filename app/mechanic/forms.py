from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed, FileSize
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length, Regexp, Optional

from ..constants import LEBANON_PHONE_REGEX, ALLOWED_CERT_EXTENSIONS, MAX_CERT_FILE_SIZE_MB

PHONE_MESSAGE = "Enter a Lebanese number in the format +961 71 234 567."


class CertificationForm(FlaskForm):
    document = FileField(
        "Certification document",
        validators=[
            FileRequired(message="Choose or drop a file to upload."),
            FileAllowed(sorted(ALLOWED_CERT_EXTENSIONS), message="Only PDF, image, or text files are accepted."),
            FileSize(max_size=MAX_CERT_FILE_SIZE_MB * 1024 * 1024, message=f"File must be under {MAX_CERT_FILE_SIZE_MB}MB."),
        ],
    )


class ProfileForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField("Phone number", validators=[DataRequired(), Regexp(LEBANON_PHONE_REGEX, message=PHONE_MESSAGE)])
    new_password = PasswordField(
        "New password (leave blank to keep current)", validators=[Optional(), Length(min=8, message="Use at least 8 characters.")]
    )
