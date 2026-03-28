"""
reset_student1_password.py

Professional debug script for UniTrack.

Reset password of student1 safely.
"""

import sys
import os

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.database import db
from app.models.user_model import User
from app.utils.security import hash_password


app = create_app()


with app.app_context():

    student = User.query.filter_by(username="student1").first()

    if not student:
        print("student1 not found")
        raise SystemExit(1)

    student.password_hash = hash_password("123456")
    student.must_change_password = False

    db.session.commit()

    print("Password reset successful")
    print("USERNAME:", student.username)
    print("NEW PASSWORD: 123456")