"""
seed_users_demo.py

Temporary helper script to create demo login users
for UniTrack authentication testing.

Teaching idea:
We do NOT create users manually in database tables.
We use the SAME service layer used by real registration.

This keeps:
- hashing correct
- duplicate protection correct
- role assignment correct
"""

import sys
import os

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.services.user_service import create_user
from app.utils.security import hash_password

app = create_app()

with app.app_context():

    demo_users = [
        {
            "first_name": "Admin",
            "last_name": "System",
            "username": "admin_demo",
            "email": "admin_demo@unitrack.com",
            "phone": "6861000001",
            "password": "Admin123!",
            "role": "administrativo",
        },
        {
            "first_name": "Docente",
            "last_name": "Test",
            "username": "docente_demo",
            "email": "docente_demo@unitrack.com",
            "phone": "6861000002",
            "password": "Docente123!",
            "role": "docente",
        },
        {
            "first_name": "Personal",
            "last_name": "Test",
            "username": "personal_demo",
            "email": "personal_demo@unitrack.com",
            "phone": "6861000003",
            "password": "Personal123!",
            "role": "personal",
        },
        {
            "first_name": "Student",
            "last_name": "Test",
            "username": "student_demo",
            "email": "student_demo@unitrack.com",
            "phone": "6861000004",
            "password": "Student123!",
            "role": "estudiante",
        },
    ]

    for u in demo_users:
        try:
            create_user(
                first_name=u["first_name"],
                last_name=u["last_name"],
                username=u["username"],
                email=u["email"],
                phone=u["phone"],
                password_hash=hash_password(u["password"]),
                role=u["role"],
            )

            print(f"CREATED -> {u['role']} : {u['username']}")

        except Exception as e:
            print(f"SKIPPED -> {u['username']} ({e})")

    print()
    print("Demo users ready.")