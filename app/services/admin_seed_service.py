"""
admin_seed_service.py

This service creates the default administrator account
if it does not already exist.

Why this matters:
The system must have one first admin account so the platform
can be configured at the beginning.

Default admin rules:
- username: Admin
- password: 12345Pp!
- role: administrativo
- must change password on first login
"""

from app.services.user_service import get_user_by_username, create_user
from app.utils.security import hash_password


def seed_default_admin():
    """
    Create the first default admin if it does not exist yet.

    Safe behavior:
    - if admin already exists, do nothing
    - if admin does not exist, create it
    """

    existing_admin = get_user_by_username("Admin")

    if existing_admin:
        return existing_admin, False

    admin_user = create_user(
        first_name="Default",
        last_name="Administrator",
        username="Admin",
        email="admin@unitrack.local",
        phone="0000000000",
        password_hash=hash_password("12345Pp!"),
        role="administrativo"
    )

    # Force first-time password change
    admin_user.must_change_password = True

    # Save this update
    from app.database import db
    db.session.commit()

    return admin_user, True