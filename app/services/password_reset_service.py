"""
password_reset_service.py

This service handles secure password reset tokens for UniTrack.

Teaching idea:
Instead of storing raw reset links directly in routes,
we centralize token generation and validation here.

Why this is professional:
- keeps auth_routes.py cleaner
- reset token logic becomes reusable
- expiration rules stay in one place
- easier to upgrade later

Architecture choice:
This version uses Flask itsdangerous serializer.

That means:
- token is signed securely with SECRET_KEY
- token can expire automatically
- we do not need a new database table for the first clean version

Later we can upgrade this with:
- database-backed reset tokens
- token revocation
- one-time-use tracking
- email template links
"""

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app

from app.services.user_service import get_user_by_email


def _get_serializer():
    """
    Create the serializer used for password reset tokens.

    Teaching idea:
    The serializer signs the token using the Flask secret key.
    If someone changes the token manually, validation fails.
    """

    secret_key = current_app.config.get("SECRET_KEY")

    if not secret_key:
        raise ValueError("SECRET_KEY is not configured")

    return URLSafeTimedSerializer(secret_key)


def generate_password_reset_token(user):
    """
    Generate a secure signed reset token for one user.

    We store only the minimum identity needed:
    - user email

    Why email:
    It is already unique in the system and easy to resolve back to the user.
    """

    if not user:
        raise ValueError("User is required to generate reset token")

    serializer = _get_serializer()

    token = serializer.dumps(
        {"email": user.email},
        salt="unitrack-password-reset"
    )

    return token


def verify_password_reset_token(token):
    """
    Validate a reset token and return the matching user.

    Security rules:
    - invalid signature = reject
    - expired token = reject
    - user not found = reject
    - inactive account = reject
    """

    if not token:
        return None, "Missing reset token"

    serializer = _get_serializer()

    max_age_seconds = int(
        current_app.config.get("PASSWORD_RESET_TOKEN_EXPIRES_MINUTES", 30)
    ) * 60

    try:
        payload = serializer.loads(
            token,
            salt="unitrack-password-reset",
            max_age=max_age_seconds
        )

    except SignatureExpired:
        return None, "This reset link has expired"

    except BadSignature:
        return None, "This reset link is invalid"

    email = str(payload.get("email", "")).strip().lower()

    if not email:
        return None, "Invalid reset token payload"

    user = get_user_by_email(email)

    if not user:
        return None, "User account not found"

    if not user.is_active_user:
        return None, "This account is inactive"

    return user, None