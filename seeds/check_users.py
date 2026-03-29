"""
check_users.py

This script prints all users in the database.

Use this for debugging:
- verify users exist
- check roles
- confirm emails / usernames
"""

import sys
import os

# 🔥 IMPORTANT: allow import from project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.models.user_model import User


app = create_app()

with app.app_context():
    users = User.query.all()

    print("\n===== USERS IN DATABASE =====\n")

    if not users:
        print("No users found.")
    else:
        for u in users:
            print(f"ID: {u.id}")
            print(f"Name: {u.first_name} {u.last_name}")
            print(f"Username: {u.username}")
            print(f"Email: {u.email}")
            print(f"Role: {u.role}")
            print(f"Active: {u.is_active_user}")
            print("-" * 40)

    print("\n===== END =====\n")