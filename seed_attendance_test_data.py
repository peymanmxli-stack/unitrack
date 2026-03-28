"""
seed_attendance_test_data.py

Temporary helper script to generate many attendance records
for pagination testing in the admin panel.

Teaching idea:
We DO NOT modify the real attendance routes for fake data.
That would be dangerous for project logic.

Instead:
we create a separate script that talks directly to the database.

What this script does:
- loads the Flask app context
- finds a target user by username
- creates many attendance records on different dates
- adds both check-in and check-out records
- helps us test pagination safely
"""

from datetime import date, time, datetime, timedelta

from app import create_app
from app.database import db
from app.models.user_model import User
from app.models.attendance_model import Attendance

app = create_app()

with app.app_context():
    # Choose the user that will receive the test attendance records.
    # IMPORTANT:
    # this must match the REAL username of the student account
    # you are currently using to log in and test attendance history.
    target_username = "peyman123"

    user = User.query.filter_by(username=target_username).first()

    if not user:
        print(f"User '{target_username}' was not found.")
        raise SystemExit()

    created_count = 0

    # We will generate 15 days of attendance.
    # Each day gets:
    # - one check-in
    # - one check-out
    #
    # Total new records:
    # 15 x 2 = 30 records
    #
    # That is enough to test pagination clearly.
    for i in range(15):
        attendance_day = date.today() - timedelta(days=i + 1)

        check_in_time = datetime.combine(attendance_day, time(8, 0, 0))
        check_out_time = datetime.combine(attendance_day, time(17, 0, 0))

        check_in_record = Attendance(
            user_id=user.id,
            movement_type="check_in",
            attendance_date=attendance_day,
            movement_time=check_in_time,
            notes=f"Seeded check-in for pagination test day {i + 1}"
        )

        check_out_record = Attendance(
            user_id=user.id,
            movement_type="check_out",
            attendance_date=attendance_day,
            movement_time=check_out_time,
            notes=f"Seeded check-out for pagination test day {i + 1}"
        )

        db.session.add(check_in_record)
        db.session.add(check_out_record)
        created_count += 2

    db.session.commit()

    print("Attendance test data created successfully.")
    print(f"Target user: {target_username}")
    print(f"New records added: {created_count}")
