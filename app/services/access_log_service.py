"""
access_log_service.py

Independent business logic for UniTrack university access control.

IMPORTANT:
This service does NOT touch teacher attendance.
Teacher attendance remains a separate academic module.

This service is only for:
- student university check-in
- student university check-out
- personal university check-in
- personal university check-out
- access log history
- hours calculation
- dashboard summary data
"""

from datetime import datetime, date, timedelta

from app.database import db
from app.models.access_log_model import AccessLog
from app.models.user_model import User


def get_current_system_datetime():
    """
    Return the current UTC datetime.

    This keeps time access centralized in one helper.
    """
    return datetime.utcnow()


def get_student_by_id(student_id):
    """
    Return one student user by id.
    """

    user = db.session.get(User, student_id)

    if not user:
        return None

    if user.role != "estudiante":
        return None

    return user


def get_personal_by_id(personal_id):
    """
    Return one personal user by id.
    """

    user = db.session.get(User, personal_id)

    if not user:
        return None

    if user.role not in {"personal", "administrativo"}:
        return None

    return user


def get_open_access_log_for_student(student_id):
    """
    Return the newest open university access log for one student.

    Open means:
    - the student already checked in
    - the student has not checked out yet
    """

    query = (
        db.select(AccessLog)
        .filter(
            AccessLog.student_id == student_id,
            AccessLog.check_out_time.is_(None),
            AccessLog.access_status == "checked_in"
        )
        .order_by(AccessLog.check_in_time.desc())
    )

    return db.session.execute(query).scalars().first()


def get_open_access_log_for_personal(personal_id):
    """
    Return the newest open university access log for one personal user.
    """

    query = (
        db.select(AccessLog)
        .filter(
            AccessLog.student_id == personal_id,
            AccessLog.check_out_time.is_(None),
            AccessLog.access_status == "checked_in"
        )
        .order_by(AccessLog.check_in_time.desc())
    )

    return db.session.execute(query).scalars().first()


def get_latest_access_log_for_student(student_id):
    """
    Return the newest access log for one student, open or closed.
    """

    query = (
        db.select(AccessLog)
        .filter(AccessLog.student_id == student_id)
        .order_by(AccessLog.check_in_time.desc())
    )

    return db.session.execute(query).scalars().first()


def get_latest_access_log_for_personal(personal_id):
    """
    Return the newest access log for one personal user, open or closed.
    """

    query = (
        db.select(AccessLog)
        .filter(AccessLog.student_id == personal_id)
        .order_by(AccessLog.check_in_time.desc())
    )

    return db.session.execute(query).scalars().first()


def calculate_minutes_between(check_in_time, check_out_time):
    """
    Return completed minutes between check-in and check-out.

    Rules:
    - if one value is missing, return 0
    - if result becomes negative, return 0
    """

    if not check_in_time or not check_out_time:
        return 0

    delta = check_out_time - check_in_time
    total_seconds = int(delta.total_seconds())

    if total_seconds <= 0:
        return 0

    return total_seconds // 60


def calculate_minutes_until_now(check_in_time):
    """
    Return elapsed minutes from check-in until now.

    Rules:
    - if check-in is missing, return 0
    - if result becomes negative, return 0
    """

    if not check_in_time:
        return 0

    now = get_current_system_datetime()
    delta = now - check_in_time
    total_seconds = int(delta.total_seconds())

    if total_seconds <= 0:
        return 0

    return total_seconds // 60


def create_check_in(student_id=None, personal_id=None, access_method="qr", notes=None):
    """
    Create a new university check-in for one student or personal user.

    Rules:
    - user must exist
    - user role must be valid
    - user cannot check in again if there is still an open access log
    """

    user_id = student_id if student_id is not None else personal_id

    if user_id is None:
        raise ValueError("User id is required")

    user = db.session.get(User, user_id)

    if not user:
        raise ValueError("User not found")

    if user.role not in {"estudiante", "personal", "administrativo"}:
        raise ValueError("User role is not allowed for access control")

    existing_open_log = get_open_access_log_for_student(user_id)

    if existing_open_log:
        raise ValueError("User already has an active check-in")

    now = get_current_system_datetime()

    new_log = AccessLog(
        student_id=user_id,
        access_date=now.date(),
        check_in_time=now,
        check_out_time=None,
        access_status="checked_in",
        access_method=access_method,
        notes=notes
    )

    try:
        db.session.add(new_log)
        db.session.commit()
        return new_log
    except Exception:
        db.session.rollback()
        raise


def create_check_out(student_id=None, personal_id=None, notes=None):
    """
    Close the active university access log for one student or personal user.

    Rules:
    - user must exist
    - there must be one active/open check-in first
    """

    user_id = student_id if student_id is not None else personal_id

    if user_id is None:
        raise ValueError("User id is required")

    user = db.session.get(User, user_id)

    if not user:
        raise ValueError("User not found")

    if user.role not in {"estudiante", "personal", "administrativo"}:
        raise ValueError("User role is not allowed for access control")

    open_log = get_open_access_log_for_student(user_id)

    if not open_log:
        raise ValueError("User does not have an active check-in")

    now = get_current_system_datetime()

    open_log.check_out_time = now
    open_log.access_status = "checked_out"

    if notes:
        open_log.notes = notes

    if hasattr(open_log, "updated_at"):
        open_log.updated_at = now

    try:
        db.session.commit()
        return open_log
    except Exception:
        db.session.rollback()
        raise


def format_minutes_as_hours_text(total_minutes):
    """
    Convert total minutes to text like:
    18h 11m
    """

    if total_minutes <= 0:
        return "0h 0m"

    hours = total_minutes // 60
    minutes = total_minutes % 60

    return f"{hours}h {minutes}m"


def calculate_hours_text(check_in_time, check_out_time):
    """
    Return a friendly duration string.

    Examples:
    6h 20m
    En curso · 2h 15m
    """

    if not check_in_time:
        return "0h 0m"

    if not check_out_time:
        running_minutes = calculate_minutes_until_now(check_in_time)
        return f"En curso · {format_minutes_as_hours_text(running_minutes)}"

    total_minutes = calculate_minutes_between(check_in_time, check_out_time)
    return format_minutes_as_hours_text(total_minutes)


def format_datetime_for_display(value):
    """
    Return datetime as display text.

    Example:
    04/25/2024 08:00 AM
    """

    if not value:
        return "--"

    return value.strftime("%m/%d/%Y %I:%M %p")


def format_time_for_display(value):
    """
    Return time as display text.

    Example:
    08:00 AM
    """

    if not value:
        return "--"

    return value.strftime("%I:%M %p")


def format_date_for_display(value):
    """
    Return date as display text.

    Example:
    04/25/2024
    """

    if not value:
        return "--"

    return value.strftime("%m/%d/%Y")


def get_student_access_logs(student_id, access_date=None):
    """
    Return access logs for one student with optional date filter.
    """

    query = db.select(AccessLog).filter(AccessLog.student_id == student_id)

    if access_date:
        query = query.filter(AccessLog.access_date == access_date)

    query = query.order_by(AccessLog.check_in_time.desc())

    return db.session.execute(query).scalars().all()


def get_personal_access_logs(personal_id, access_date=None):
    """
    Return access logs for one personal user with optional date filter.
    """

    query = db.select(AccessLog).filter(AccessLog.student_id == personal_id)

    if access_date:
        query = query.filter(AccessLog.access_date == access_date)

    query = query.order_by(AccessLog.check_in_time.desc())

    return db.session.execute(query).scalars().all()


def build_student_access_table_rows(student):
    """
    Build frontend-ready rows for the access control table.
    """

    logs = get_student_access_logs(student.id)

    rows = []

    for index, log in enumerate(logs, start=1):
        rows.append(
            {
                "row": index,
                "name": student.full_name(),
                "matricula": student.username,
                "class_name": "University Access",
                "date": format_date_for_display(log.access_date),
                "check_in": format_time_for_display(log.check_in_time),
                "check_out": format_time_for_display(log.check_out_time),
                "hours": calculate_hours_text(log.check_in_time, log.check_out_time),
                "status": log.access_status
            }
        )

    return rows


def build_personal_access_table_rows(personal):
    """
    Build frontend-ready rows for the access control table.
    """

    logs = get_personal_access_logs(personal.id)

    rows = []

    for index, log in enumerate(logs, start=1):
        rows.append(
            {
                "row": index,
                "name": personal.full_name(),
                "matricula": personal.username,
                "class_name": "University Access",
                "date": format_date_for_display(log.access_date),
                "check_in": format_time_for_display(log.check_in_time),
                "check_out": format_time_for_display(log.check_out_time),
                "hours": calculate_hours_text(log.check_in_time, log.check_out_time),
                "status": log.access_status
            }
        )

    return rows


def get_today_first_check_in(student_id):
    """
    Return today's first check-in time text for one student.
    """

    today = get_current_system_datetime().date()

    query = (
        db.select(AccessLog)
        .filter(
            AccessLog.student_id == student_id,
            AccessLog.access_date == today
        )
        .order_by(AccessLog.check_in_time.asc())
    )

    first_log = db.session.execute(query).scalars().first()

    if not first_log:
        return "--"

    return format_time_for_display(first_log.check_in_time)


def get_today_first_check_in_for_personal(personal_id):
    """
    Return today's first check-in time text for one personal user.
    """

    today = get_current_system_datetime().date()

    query = (
        db.select(AccessLog)
        .filter(
            AccessLog.student_id == personal_id,
            AccessLog.access_date == today
        )
        .order_by(AccessLog.check_in_time.asc())
    )

    first_log = db.session.execute(query).scalars().first()

    if not first_log:
        return "--"

    return format_time_for_display(first_log.check_in_time)


def get_today_completed_minutes(student_id):
    """
    Return total completed minutes for today.

    Only fully completed logs are counted here.
    """

    today = get_current_system_datetime().date()

    query = (
        db.select(AccessLog)
        .filter(
            AccessLog.student_id == student_id,
            AccessLog.access_date == today
        )
        .order_by(AccessLog.check_in_time.asc())
    )

    logs = db.session.execute(query).scalars().all()

    total_minutes = 0

    for log in logs:
        total_minutes += calculate_minutes_between(
            log.check_in_time,
            log.check_out_time
        )

    return total_minutes


def get_today_completed_minutes_for_personal(personal_id):
    """
    Return total completed minutes for today for one personal user.
    """

    today = get_current_system_datetime().date()

    query = (
        db.select(AccessLog)
        .filter(
            AccessLog.student_id == personal_id,
            AccessLog.access_date == today
        )
        .order_by(AccessLog.check_in_time.asc())
    )

    logs = db.session.execute(query).scalars().all()

    total_minutes = 0

    for log in logs:
        total_minutes += calculate_minutes_between(
            log.check_in_time,
            log.check_out_time
        )

    return total_minutes


def get_today_running_minutes(student_id):
    """
    Return elapsed minutes for today's current open session.

    If there is no active session today, return 0.
    """

    today = get_current_system_datetime().date()
    open_log = get_open_access_log_for_student(student_id)

    if not open_log:
        return 0

    if open_log.access_date != today:
        return 0

    return calculate_minutes_until_now(open_log.check_in_time)


def get_today_running_minutes_for_personal(personal_id):
    """
    Return elapsed minutes for today's current open session for one personal user.
    """

    today = get_current_system_datetime().date()
    open_log = get_open_access_log_for_personal(personal_id)

    if not open_log:
        return 0

    if open_log.access_date != today:
        return 0

    return calculate_minutes_until_now(open_log.check_in_time)


def get_today_total_minutes(student_id):
    """
    Return total minutes for today including:
    - completed sessions
    - active running session
    """

    completed_minutes = get_today_completed_minutes(student_id)
    running_minutes = get_today_running_minutes(student_id)

    return completed_minutes + running_minutes


def get_today_total_minutes_for_personal(personal_id):
    """
    Return total minutes for today for one personal user including:
    - completed sessions
    - active running session
    """

    completed_minutes = get_today_completed_minutes_for_personal(personal_id)
    running_minutes = get_today_running_minutes_for_personal(personal_id)

    return completed_minutes + running_minutes


def get_week_access_days_count(student_id):
    """
    Return how many distinct days the student has access logs
    during the last 7 days including today.
    """

    today = get_current_system_datetime().date()
    start_date = today - timedelta(days=6)

    query = (
        db.select(AccessLog.access_date)
        .filter(
            AccessLog.student_id == student_id,
            AccessLog.access_date >= start_date,
            AccessLog.access_date <= today
        )
        .distinct()
    )

    days = db.session.execute(query).all()

    return len(days)


def get_week_access_days_count_for_personal(personal_id):
    """
    Return how many distinct days the personal user has access logs
    during the last 7 days including today.
    """

    today = get_current_system_datetime().date()
    start_date = today - timedelta(days=6)

    query = (
        db.select(AccessLog.access_date)
        .filter(
            AccessLog.student_id == personal_id,
            AccessLog.access_date >= start_date,
            AccessLog.access_date <= today
        )
        .distinct()
    )

    days = db.session.execute(query).all()

    return len(days)


def get_month_total_minutes(student_id):
    """
    Return total completed minutes for the current month.
    """

    now = get_current_system_datetime()
    month_start = date(now.year, now.month, 1)

    if now.month == 12:
        next_month_start = date(now.year + 1, 1, 1)
    else:
        next_month_start = date(now.year, now.month + 1, 1)

    query = (
        db.select(AccessLog)
        .filter(
            AccessLog.student_id == student_id,
            AccessLog.access_date >= month_start,
            AccessLog.access_date < next_month_start
        )
        .order_by(AccessLog.check_in_time.asc())
    )

    logs = db.session.execute(query).scalars().all()

    total_minutes = 0

    for log in logs:
        if log.check_out_time:
            total_minutes += calculate_minutes_between(
                log.check_in_time,
                log.check_out_time
            )
        else:
            total_minutes += calculate_minutes_until_now(log.check_in_time)

    return total_minutes


def get_month_total_minutes_for_personal(personal_id):
    """
    Return total completed minutes for the current month for one personal user.
    """

    now = get_current_system_datetime()
    month_start = date(now.year, now.month, 1)

    if now.month == 12:
        next_month_start = date(now.year + 1, 1, 1)
    else:
        next_month_start = date(now.year, now.month + 1, 1)

    query = (
        db.select(AccessLog)
        .filter(
            AccessLog.student_id == personal_id,
            AccessLog.access_date >= month_start,
            AccessLog.access_date < next_month_start
        )
        .order_by(AccessLog.check_in_time.asc())
    )

    logs = db.session.execute(query).scalars().all()

    total_minutes = 0

    for log in logs:
        if log.check_out_time:
            total_minutes += calculate_minutes_between(
                log.check_in_time,
                log.check_out_time
            )
        else:
            total_minutes += calculate_minutes_until_now(log.check_in_time)

    return total_minutes


def get_student_access_quick_stats(student_id):
    """
    Return dashboard quick stats for the student access module.
    """

    week_days = get_week_access_days_count(student_id)
    month_minutes = get_month_total_minutes(student_id)

    return {
        "today_check_in": get_today_first_check_in(student_id),
        "week_days": f"{week_days} días registrados",
        "month_hours": format_minutes_as_hours_text(month_minutes)
    }


def get_personal_access_quick_stats(personal_id):
    """
    Return dashboard quick stats for the personal access module.
    """

    week_days = get_week_access_days_count_for_personal(personal_id)
    month_minutes = get_month_total_minutes_for_personal(personal_id)

    return {
        "today_check_in": get_today_first_check_in_for_personal(personal_id),
        "week_days": f"{week_days} días registrados",
        "month_hours": format_minutes_as_hours_text(month_minutes)
    }


def get_student_current_access_status(student_id):
    """
    Return current access state for the student.
    """

    open_log = get_open_access_log_for_student(student_id)
    latest_log = get_latest_access_log_for_student(student_id)
    today_minutes = get_today_total_minutes(student_id)

    if not open_log:
        if not latest_log:
            return {
                "status": "checked_out",
                "last_check_in": "--",
                "last_check_out": "--",
                "hours_today": format_minutes_as_hours_text(today_minutes)
            }

        return {
            "status": "checked_out",
            "last_check_in": format_time_for_display(latest_log.check_in_time),
            "last_check_out": format_time_for_display(latest_log.check_out_time),
            "hours_today": format_minutes_as_hours_text(today_minutes)
        }

    return {
        "status": "checked_in",
        "last_check_in": format_time_for_display(open_log.check_in_time),
        "last_check_out": "Pendiente",
        "hours_today": format_minutes_as_hours_text(today_minutes)
    }


def get_personal_current_access_status(personal_id):
    """
    Return current access state for the personal user.
    """

    open_log = get_open_access_log_for_personal(personal_id)
    latest_log = get_latest_access_log_for_personal(personal_id)
    today_minutes = get_today_total_minutes_for_personal(personal_id)

    if not open_log:
        if not latest_log:
            return {
                "status": "checked_out",
                "last_check_in": "--",
                "last_check_out": "--",
                "hours_today": format_minutes_as_hours_text(today_minutes)
            }

        return {
            "status": "checked_out",
            "last_check_in": format_time_for_display(latest_log.check_in_time),
            "last_check_out": format_time_for_display(latest_log.check_out_time),
            "hours_today": format_minutes_as_hours_text(today_minutes)
        }

    return {
        "status": "checked_in",
        "last_check_in": format_time_for_display(open_log.check_in_time),
        "last_check_out": "Pendiente",
        "hours_today": format_minutes_as_hours_text(today_minutes)
    }