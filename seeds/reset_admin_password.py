"""
reset_admin_password.py

Temporary helper script for UniTrack.

Teaching idea:
Sometimes during development we forget the current password.

Instead of guessing many times,
we safely reset the admin password from the database.

This script:
- opens the Flask app context
- finds the Admin user
- sets a new known password hash
- saves it to the database

IMPORTANT:
This is a development helper.
Later in production, password resets should happen
through a secure admin workflow, not with a script.
"""

import sys
import os

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.database import db
from app.models.user_model import User
from app.utils.security import hash_password


NEW_PASSWORD = "Admin12345!"


app = create_app()

with app.app_context():
    admin_user = User.query.filter_by(username="Admin").first()

    if not admin_user:
        print("Admin user was not found.")
    else:
        admin_user.password_hash = hash_password(NEW_PASSWORD)
        admin_user.must_change_password = False
        db.session.commit()

        print("Admin password reset successfully.")
        print(f"Username: {admin_user.username}")
        print(f"New password: {NEW_PASSWORD}")