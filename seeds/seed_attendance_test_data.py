import sys
import os

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

"""
seed_attendance_test_data.py

Temporary helper script to generate attendance records
for testing the student/admin attendance history pages.

NEW VERSION:
This script now matches the real UniTrack Attendance model.

Real model fields:
- session_id
- student_id
- status
- notes

Important:
Attendance is session-based now, so we must attach each row
to a real class session that already exists in the database.
"""

from app import create_app
from app.database import db
from app.models.user_model import User
from app.models.attendance_model import Attendance

app = create_app()

with app.app_context():
    # Use the REAL username you want to test
    target_username = "michael123"

    student = User.query.filter_by(username=target_username).first()

    if not student:
        print(f"User '{target_username}' was not found.")
        raise SystemExit()

    # Get real class session IDs from database
    session_rows = db.session.execute(
        db.text("""
            SELECT id
            FROM class_sessions
            ORDER BY id ASC
            LIMIT 15
        """)
    ).fetchall()

    if not session_rows:
        print("No class sessions were found in the database.")
        print("Create class sessions first before seeding attendance.")
        raise SystemExit()

    created_count = 0
    status_cycle = [
        "present",
        "present",
        "present",
        "late",
        "absent",
    ]

    for index, row in enumerate(session_rows):
        session_id = row[0]
        status_value = status_cycle[index % len(status_cycle)]

        # Optional safety:
        # avoid inserting duplicate attendance for same student + session
        existing_attendance = Attendance.query.filter_by(
            session_id=session_id,
            student_id=student.id
        ).first()

        if existing_attendance:
            continue

        attendance_record = Attendance(
            session_id=session_id,
            student_id=student.id,
            status=status_value,
            notes=f"Seeded attendance test record #{index + 1}"
        )

        db.session.add(attendance_record)
        created_count += 1

    db.session.commit()

    print("Attendance test data created successfully.")
    print(f"Target user: {target_username}")
    print(f"Sessions found: {len(session_rows)}")
    print(f"New attendance rows added: {created_count}")