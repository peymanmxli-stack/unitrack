"""
validation_code_service.py

Business logic for UniTrack validation codes.

Teaching idea:
This service is the brain behind the validation code system.

Routes should not directly contain all database logic.
Instead:

route -> service -> model -> database

Main responsibilities:
- create new validation codes
- find codes
- validate codes
- mark codes as used
"""

from datetime import datetime, timedelta
import secrets
import string

from app.database import db
from app.models.validation_code_model import ValidationCode


def generate_random_code(length=8):
    """
    Generate a secure random validation code.

    Why we use uppercase letters and numbers:
    - easy to read
    - easy to type
    - looks professional
    - good enough for university internal use
    """
    characters = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


def generate_unique_code(length=8):
    """
    Generate a code that does not already exist in the database.

    Important:
    We keep trying until we find a unique one.
    """
    while True:
        code = generate_random_code(length=length)

        existing_code = get_validation_code_by_code(code)
        if not existing_code:
            return code


def create_validation_code(generated_by_user_id, expires_in_hours=24):
    """
    Create and save a new validation code.

    Parameters:
    - generated_by_user_id: admin user id
    - expires_in_hours: how many hours the code remains valid

    Returns:
    - created ValidationCode object
    """
    if not generated_by_user_id:
        raise ValueError("generated_by_user_id is required")

    code = generate_unique_code(length=8)

    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

    validation_code = ValidationCode(
        code=code,
        generated_by=generated_by_user_id,
        expires_at=expires_at
    )

    try:
        db.session.add(validation_code)
        db.session.commit()
        return validation_code
    except Exception:
        db.session.rollback()
        raise


def get_validation_code_by_code(code):
    """
    Find one validation code by its text value.
    """
    if not code:
        return None

    clean_code = str(code).strip().upper()

    return db.session.execute(
        db.select(ValidationCode).filter_by(code=clean_code)
    ).scalar_one_or_none()


def validate_code_for_use(code):
    """
    Check if a validation code exists and is still usable.

    Returns:
    - (True, validation_code_object, None) if valid
    - (False, None, error_message) if invalid
    """
    validation_code = get_validation_code_by_code(code)

    if not validation_code:
        return False, None, "Validation code not found"

    if validation_code.is_used:
        return False, None, "Validation code has already been used"

    if validation_code.is_expired():
        return False, None, "Validation code has expired"

    return True, validation_code, None


def mark_validation_code_as_used(validation_code, used_by_user_id):
    """
    Mark a validation code as consumed.

    Why this matters:
    - one code should not be reused many times
    - we keep audit history
    - admin can later track who used which code
    """
    if not validation_code:
        return None

    try:
        validation_code.is_used = True
        validation_code.used_at = datetime.utcnow()
        validation_code.used_by_user_id = used_by_user_id

        db.session.commit()
        return validation_code
    except Exception:
        db.session.rollback()
        raise