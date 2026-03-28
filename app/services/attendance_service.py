"""
attendance_service.py

Docente attendance business logic layer.

Lifecycle:
open session -> mark attendance -> auto finalize -> close -> reopen -> edit -> close again

Now upgraded with:
- server-side session filtering support
- bulk attendance support
- student attendance history support
- auto-created not_marked rows when a session opens
"""

from datetime import datetime

from app.database import db
from app.models.attendance_model import Attendance
from app.models.class_group_model import ClassGroup
from app.models.class_session_model import ClassSession
from app.models.user_model import User
from app.services.enrollment_service import get_active_students_by_class


ALLOWED_ATTENDANCE_STATUSES = {"present", "late", "absent"}
DEFAULT_SESSION_ATTENDANCE_STATUS = "not_marked"


def get_current_system_datetime():
    return datetime.utcnow()


def get_teacher_class_groups(teacher_id, only_active=True):
    query = db.select(ClassGroup).filter_by(teacher_id=teacher_id)

    if only_active:
        query = query.filter_by(is_active=True)

    query = query.order_by(ClassGroup.subject_name.asc(), ClassGroup.group_code.asc())

    return db.session.execute(query).scalars().all()


def get_class_group_by_id(class_group_id):
    return db.session.get(ClassGroup, class_group_id)


def get_open_session_for_class(class_group_id):
    query = (
        db.select(ClassSession)
        .filter_by(class_group_id=class_group_id, is_open=True)
        .order_by(ClassSession.created_at.desc())
    )

    return db.session.execute(query).scalars().first()


def get_class_session_by_id(session_id):
    return db.session.get(ClassSession, session_id)


def reopen_class_session(session_id, teacher_id):
    session = get_class_session_by_id(session_id)

    if not session:
        raise ValueError("Class session not found")

    if session.teacher_id != teacher_id:
        raise ValueError("You do not own this class session")

    if session.is_open:
        raise ValueError("Session is already open")

    session.is_open = True
    session.end_time = None
    session.updated_at = get_current_system_datetime()

    try:
        db.session.commit()
        return session
    except Exception:
        db.session.rollback()
        raise


def create_initial_attendance_rows_for_session(session):
    """
    Create one initial attendance row for every enrolled student.

    Why this exists:
    The teacher chose option B.

    So when a session is opened, the roster is immediately ready and every
    student starts with a stable backend status: not_marked.
    """
    students = get_active_students_by_class(session.class_group_id)
    now = get_current_system_datetime()

    for student in students:
        db.session.add(Attendance(
            session_id=session.id,
            student_id=student.id,
            status=DEFAULT_SESSION_ATTENDANCE_STATUS,
            notes=None,
            created_at=now,
            updated_at=now
        ))


def create_class_session(class_group_id, teacher_id, notes=None):
    class_group = get_class_group_by_id(class_group_id)

    if not class_group:
        raise ValueError("Class group not found")

    if not class_group.is_active:
        raise ValueError("This class group is inactive")

    if class_group.teacher_id != teacher_id:
        raise ValueError("You do not own this class group")

    existing_open_session = get_open_session_for_class(class_group_id)

    if existing_open_session:
        raise ValueError("This class already has an open session")

    now = get_current_system_datetime()

    session = ClassSession(
        class_group_id=class_group_id,
        teacher_id=teacher_id,
        session_date=now.date(),
        start_time=now,
        notes=notes,
        is_open=True
    )

    try:
        db.session.add(session)
        db.session.flush()

        create_initial_attendance_rows_for_session(session)

        db.session.commit()
        return session
    except Exception:
        db.session.rollback()
        raise


def get_attendance_record_for_student(session_id, student_id):
    query = db.select(Attendance).filter_by(
        session_id=session_id,
        student_id=student_id
    )

    return db.session.execute(query).scalars().first()


def mark_student_attendance(session_id, teacher_id, student_id, status, notes=None):
    if status not in ALLOWED_ATTENDANCE_STATUSES:
        raise ValueError("Invalid attendance status")

    session = get_class_session_by_id(session_id)

    if not session:
        raise ValueError("Class session not found")

    if session.teacher_id != teacher_id:
        raise ValueError("You do not own this class session")

    if not session.is_open:
        raise ValueError("Cannot mark attendance in a closed session")

    student = db.session.get(User, student_id)

    if not student:
        raise ValueError("Student not found")

    if student.role != "estudiante":
        raise ValueError("Attendance can only be marked for students")

    enrollment_exists = db.session.execute(
        db.select(User.id)
        .join(User.student_class_enrollments)
        .filter(
            User.id == student_id,
            User.student_class_enrollments.any(
                class_group_id=session.class_group_id,
                is_active=True
            )
        )
    ).first()

    if not enrollment_exists:
        raise ValueError("Student is not enrolled in this class roster")

    existing_record = get_attendance_record_for_student(session_id, student_id)

    try:
        if existing_record:
            existing_record.status = status
            existing_record.notes = notes
            existing_record.updated_at = get_current_system_datetime()
            db.session.commit()
            return existing_record

        new_record = Attendance(
            session_id=session_id,
            student_id=student_id,
            status=status,
            notes=notes
        )

        db.session.add(new_record)
        db.session.commit()
        return new_record

    except Exception:
        db.session.rollback()
        raise


def mark_bulk_attendance(session_id, teacher_id, attendance_items):
    if not isinstance(attendance_items, list) or not attendance_items:
        raise ValueError("attendance_items must be a non-empty list")

    session = get_class_session_by_id(session_id)

    if not session:
        raise ValueError("Class session not found")

    if session.teacher_id != teacher_id:
        raise ValueError("You do not own this class session")

    if not session.is_open:
        raise ValueError("Cannot mark attendance in a closed session")

    saved_records = []

    for item in attendance_items:
        student_id = item.get("student_id")
        status = item.get("status")
        notes = item.get("notes")

        if not student_id:
            raise ValueError("Each attendance item must include student_id")

        if status not in ALLOWED_ATTENDANCE_STATUSES:
            raise ValueError("Each attendance item must include valid status")

        record = mark_student_attendance(
            session_id=session_id,
            teacher_id=teacher_id,
            student_id=student_id,
            status=status,
            notes=notes
        )

        saved_records.append(record)

    return saved_records


def auto_finalize_attendance(session):
    students = get_active_students_by_class(session.class_group_id)
    existing_records = get_attendance_records_by_session(session.id)

    existing_by_student = {r.student_id: r for r in existing_records}
    now = get_current_system_datetime()

    for student in students:
        record = existing_by_student.get(student.id)

        if not record:
            db.session.add(Attendance(
                session_id=session.id,
                student_id=student.id,
                status="absent",
                notes="Auto-marked absent on session close",
                created_at=now,
                updated_at=now
            ))
            continue

        if record.status == DEFAULT_SESSION_ATTENDANCE_STATUS:
            record.status = "absent"
            record.notes = "Auto-marked absent on session close"
            record.updated_at = now


def close_class_session(session_id, teacher_id):
    session = get_class_session_by_id(session_id)

    if not session:
        raise ValueError("Class session not found")

    if session.teacher_id != teacher_id:
        raise ValueError("You do not own this class session")

    if not session.is_open:
        raise ValueError("This class session is already closed")

    auto_finalize_attendance(session)

    session.is_open = False
    session.end_time = get_current_system_datetime()
    session.updated_at = get_current_system_datetime()

    try:
        db.session.commit()
        return session
    except Exception:
        db.session.rollback()
        raise


def get_attendance_records_by_session(session_id):
    query = (
        db.select(Attendance)
        .filter_by(session_id=session_id)
        .order_by(Attendance.created_at.asc())
    )

    return db.session.execute(query).scalars().all()


def get_sessions_by_teacher(
    teacher_id,
    only_open=False,
    search=None,
    status=None,
    session_date=None
):
    query = db.select(ClassSession).join(ClassGroup)
    query = query.filter(ClassSession.teacher_id == teacher_id)

    if status == "open":
        query = query.filter(ClassSession.is_open.is_(True))
    elif status == "closed":
        query = query.filter(ClassSession.is_open.is_(False))
    elif only_open:
        query = query.filter(ClassSession.is_open.is_(True))

    if session_date:
        query = query.filter(ClassSession.session_date == session_date)

    if search:
        search_term = f"%{search.lower()}%"

        query = query.filter(
            db.or_(
                db.func.lower(ClassGroup.subject_name).like(search_term),
                db.func.lower(ClassGroup.group_code).like(search_term),
                db.cast(ClassSession.id, db.String).like(search_term)
            )
        )

    query = query.order_by(ClassSession.created_at.desc())

    return db.session.execute(query).scalars().all()


def format_attendance_status_for_ui(status):
    status = (status or "").strip().lower()

    if status == "present":
        return "Present"
    if status == "late":
        return "Late"
    if status == "not_marked":
        return "Not Marked"
    return "Absent"


def format_attendance_date_for_ui(session_date):
    if not session_date:
        return ""
    return session_date.strftime("%m/%d/%Y")


def format_attendance_time_for_ui(session):
    if session and session.start_time:
        return session.start_time.strftime("%I:%M %p")
    return "--:--"


def build_attendance_class_name(class_group):
    if not class_group:
        return "--"

    subject_name = (class_group.subject_name or "").strip()
    group_code = (class_group.group_code or "").strip()

    if subject_name and group_code:
        return f"{subject_name} - {group_code}"
    if subject_name:
        return subject_name
    if group_code:
        return group_code

    return "--"


def build_teacher_name_for_ui(teacher):
    if not teacher:
        return "--"

    first_name = (teacher.first_name or "").strip()
    last_name = (teacher.last_name or "").strip()
    full_name = f"{first_name} {last_name}".strip()

    return full_name if full_name else "--"


def get_student_attendance_history_records(student_id, selected_date=None, selected_class_name=None):
    teacher_alias = db.aliased(User)

    query = (
        db.session.query(Attendance, ClassSession, ClassGroup, teacher_alias)
        .join(ClassSession, Attendance.session_id == ClassSession.id)
        .join(ClassGroup, ClassSession.class_group_id == ClassGroup.id)
        .join(teacher_alias, ClassSession.teacher_id == teacher_alias.id)
        .filter(Attendance.student_id == student_id)
        .filter(Attendance.status != DEFAULT_SESSION_ATTENDANCE_STATUS)
    )

    if selected_date:
        try:
            parsed_date = datetime.strptime(selected_date, "%m/%d/%Y").date()
            query = query.filter(ClassSession.session_date == parsed_date)
        except ValueError:
            pass

    if selected_class_name:
        query = query.filter(ClassGroup.subject_name == selected_class_name)

    query = query.order_by(
        ClassSession.session_date.desc(),
        ClassSession.start_time.desc(),
        Attendance.created_at.desc()
    )

    return query.all()


def build_student_attendance_history_rows(student_id, selected_date=None, selected_class_name=None):
    results = get_student_attendance_history_records(
        student_id=student_id,
        selected_date=selected_date,
        selected_class_name=selected_class_name
    )

    rows = []

    for index, (attendance, session, class_group, teacher) in enumerate(results, start=1):
        rows.append({
            "row": index,
            "attendance_id": attendance.id,
            "date": format_attendance_date_for_ui(session.session_date),
            "time": format_attendance_time_for_ui(session),
            "class_name": class_group.subject_name if class_group else "--",
            "class_display_name": build_attendance_class_name(class_group),
            "teacher_name": build_teacher_name_for_ui(teacher),
            "status": format_attendance_status_for_ui(attendance.status),
            "notes": attendance.notes if attendance.notes else ""
        })

    return rows


def get_student_attendance_class_options(student_id):
    query = (
        db.session.query(ClassGroup.subject_name)
        .join(ClassSession, ClassSession.class_group_id == ClassGroup.id)
        .join(Attendance, Attendance.session_id == ClassSession.id)
        .filter(Attendance.student_id == student_id)
        .filter(Attendance.status != DEFAULT_SESSION_ATTENDANCE_STATUS)
        .distinct()
        .order_by(ClassGroup.subject_name.asc())
    )

    return [row[0] for row in query.all() if row[0]]


def get_student_attendance_summary(student_id, selected_date=None, selected_class_name=None):
    rows = build_student_attendance_history_rows(
        student_id=student_id,
        selected_date=selected_date,
        selected_class_name=selected_class_name
    )

    present_count = sum(1 for row in rows if row["status"] == "Present")
    late_count = sum(1 for row in rows if row["status"] == "Late")
    absent_count = sum(1 for row in rows if row["status"] == "Absent")

    total_count = len(rows)
    attended_count = present_count + late_count

    attendance_percentage = 0

    if total_count > 0:
        attendance_percentage = round((attended_count / total_count) * 100)

    if attendance_percentage > 90:
        attendance_percentage_color = "green"
    elif 80 <= attendance_percentage <= 90:
        attendance_percentage_color = "yellow"
    else:
        attendance_percentage_color = "red"

    return {
        "attendance_percentage": attendance_percentage,
        "attendance_percentage_color": attendance_percentage_color,
        "present_count": present_count,
        "late_count": late_count,
        "absent_count": absent_count,
        "total_count": total_count,
        "missed_days": absent_count
    }


def build_personal_attendance_history_rows(personal_id, selected_date=None, selected_class_name=None):
    return build_student_attendance_history_rows(
        student_id=personal_id,
        selected_date=selected_date,
        selected_class_name=selected_class_name
    )


def get_personal_attendance_class_options(personal_id):
    return get_student_attendance_class_options(student_id=personal_id)


def get_personal_attendance_summary(personal_id, selected_date=None, selected_class_name=None):
    return get_student_attendance_summary(
        student_id=personal_id,
        selected_date=selected_date,
        selected_class_name=selected_class_name
    )