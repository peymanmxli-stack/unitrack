"""
reset_docente_password.py

Development helper for UniTrack.

Resets password of testdocente user
so we can continue attendance testing.
"""

import sys
import os

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.database import db
from app.models.user_model import User
from app.utils.security import hash_password


NEW_PASSWORD = "Docente123!"


app = create_app()

with app.app_context():
    user = User.query.filter_by(username="testdocente").first()

    if not user:
        print("Docente user not found.")
    else:
        user.password_hash = hash_password(NEW_PASSWORD)
        user.must_change_password = False
        db.session.commit()

        print("Docente password reset successfully.")
        print(f"Username: {user.username}")
        print(f"New password: {NEW_PASSWORD}")