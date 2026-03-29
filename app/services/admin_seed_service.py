"""
admin_seed_service.py

This service creates the default administrator account
if it does not already exist.

Why this matters:
The system must have one first admin account so the platform
can be configured at the beginning.

Startup behavior:
- if admin already exists, do nothing
- if admin does not exist, create it automatically
- works for local and Render startup
- uses environment values if available
"""

import os

from app.services.user_service import get_user_by_username, create_user
from app.utils.security import hash_password
from app.database import db


def seed_default_admin():
    """
    Create the first default admin if it does not exist yet.

    Safe behavior:
    - if admin already exists, do nothing
    - if admin does not exist, create it
    """

    admin_username = os.environ.get("DEFAULT_ADMIN_USERNAME", "Admin").strip()
    admin_first_name = os.environ.get("DEFAULT_ADMIN_FIRST_NAME", "Default").strip()
    admin_last_name = os.environ.get("DEFAULT_ADMIN_LAST_NAME", "Administrator").strip()
    admin_email = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@unitrack.local").strip().lower()
    admin_phone = os.environ.get("DEFAULT_ADMIN_PHONE", "0000000000").strip()
    admin_password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "12345Pp!").strip()

    existing_admin = get_user_by_username(admin_username)

    if existing_admin:
        # Make sure startup admin is usable
        changed = False

        if not existing_admin.is_active_user:
            existing_admin.is_active_user = True
            changed = True

        if not existing_admin.must_change_password:
            existing_admin.must_change_password = True
            changed = True

        if changed:
            db.session.commit()

        return existing_admin, False

    admin_user = create_user(
        first_name=admin_first_name,
        last_name=admin_last_name,
        username=admin_username,
        email=admin_email,
        phone=admin_phone,
        password_hash=hash_password(admin_password),
        role="administrativo"
    )

    # Force first-time password change
    admin_user.must_change_password = True
    admin_user.is_active_user = True

    db.session.commit()

    return admin_user, True