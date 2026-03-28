import sys
import os

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timedelta

from app import create_app
from app.database import db
from app.models.user_model import User
from app.models.class_group_model import ClassGroup
from app.models.class_session_model import ClassSession
from app.models.attendance_model import Attendance
from app.services.enrollment_service import enroll_student_in_class

app = create_app()

with app.app_context():

    # 🔹 1. USERS
    student = User.query.filter_by(username="peyman123").first()
    teacher = User.query.filter_by(username="docente_demo").first()

    if not student:
        print("Student not found")
        raise SystemExit()

    if not teacher:
        print("Teacher not found (run seed_users_demo first)")
        raise SystemExit()

    # 🔹 2. CLASS GROUP
    class_group = ClassGroup.query.filter_by(
        subject_name="Databases",
        group_code="3AFM"
    ).first()

    if not class_group:
        class_group = ClassGroup(
            subject_name="Databases",
            group_code="3AFM",
            teacher_id=teacher.id
        )
        db.session.add(class_group)
        db.session.commit()
        print("Class group created")

    # 🔹 3. ENROLLMENT
    try:
        enroll_student_in_class(class_group.id, student.id)
        print("Student enrolled")
    except Exception as e:
        print("Enrollment skipped:", e)

    # 🔹 4. CLASS SESSIONS
    sessions = []

    for i in range(10):
        session_date = datetime.utcnow().date() - timedelta(days=i)

        session = ClassSession(
            class_group_id=class_group.id,
            teacher_id=teacher.id,
            session_date=session_date,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            notes=f"Session {i+1}",
            is_open=False
        )

        db.session.add(session)
        sessions.append(session)

    db.session.commit()
    print("Sessions created:", len(sessions))

    # 🔹 5. ATTENDANCE
    statuses = ["present", "present", "late", "absent"]

    created = 0

    for i, session in enumerate(sessions):
        status = statuses[i % len(statuses)]

        existing = Attendance.query.filter_by(
            session_id=session.id,
            student_id=student.id
        ).first()

        if existing:
            continue

        attendance = Attendance(
            session_id=session.id,
            student_id=student.id,
            status=status,
            notes=f"Auto seed {i+1}"
        )

        db.session.add(attendance)
        created += 1

    db.session.commit()

    print("Attendance created:", created)
    print("DONE ✅")