"""
seed_verification_code.py

Create one manual validation code for UniTrack registration.

Current project behavior:
- finds the default admin user
- creates one new validation code
- saves it in the database

Updated behavior:
- each execution generates a NEW unique validation code
- expiration stays configurable
- prints the created code clearly

Usage:
    python seed_verification_code.py
"""

import os
import sys

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.models.user_model import User
from app.services.validation_code_service import create_validation_code


app = create_app()


with app.app_context():
    admin_user = User.query.filter_by(username="Admin").first()

    if not admin_user:
        print("ERROR: Admin user was not found.")
        print("Make sure your default admin seed is working first.")
    else:
        try:
            validation_code = create_validation_code(
                generated_by_user_id=admin_user.id,
                expires_in_hours=24 * 7
            )

            print("Validation code created successfully:", validation_code.code)
            print("Expires at:", validation_code.expires_at)

        except Exception as error:
            print("ERROR: Failed to create validation code.")
            print(str(error))