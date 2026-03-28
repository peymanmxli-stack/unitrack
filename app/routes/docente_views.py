"""
docente_views.py

Teacher UI rendering routes.

Architecture Fix:
- dashboard route unified to /docente/dashboard
- classes page route added
- session history kept
- safer redirects
- roster flow preserved
- analytics page route added professionally
- export center page route added
- filtered multi-session CSV export added

Teaching idea:
This file controls the teacher HTML pages and browser actions.
I keep page rendering here and keep business logic inside services.
That makes the project cleaner and easier to maintain.

New analytics idea:
I now prepare teacher-friendly analytics data here so the HTML page
can focus on presentation instead of calculations.

That means:
- attendance percentages are calculated here
- summary cards are calculated here
- recent trend data is prepared here
- ownership/security still stays protected
- export reporting stays centralized and safe

New roster polish:
I now expose one official frontend field for roster lock behavior:

attendance_history_locked

Why this helps:
Before, the template had to guess several possible field names.
Now the backend always sends one stable key, and the UI can trust it.
"""

from math import ceil
from datetime import datetime
import csv
from io import StringIO

from flask import Blueprint, render_template, request, redirect, Response
from flask_login import login_required, current_user

from app.services.attendance_service import (
    get_teacher_class_groups,
    get_sessions_by_teacher,
    get_attendance_records_by_session,
    get_class_session_by_id,
    create_class_session,
    close_class_session,
    reopen_class_session,
)

from app.services.enrollment_service import get_active_students_by_class


docente_views_bp = Blueprint("docente_views", __name__)


# =========================================================
# GUARD
# =========================================================
def docente_page_guard():
    """
    Small protection helper for teacher pages.

    I use this helper so every teacher page has the same security rule:
    - user must be active
    - user must have docente role
    """
    if not current_user.is_active_user:
        return False

    if current_user.role != "docente":
        return False

    return True


# =========================================================
# SUMMARY BUILDER
# =========================================================
def build_attendance_summary(total_students, records):
    """
    Build stable summary numbers for templates.

    I calculate this once here so the HTML page stays simple.
    """
    present_count = sum(1 for record in records if record.status == "present")
    late_count = sum(1 for record in records if record.status == "late")
    absent_count = sum(1 for record in records if record.status == "absent")

    marked_count = present_count + late_count + absent_count
    not_marked_count = total_students - marked_count

    if not_marked_count < 0:
        not_marked_count = 0

    return {
        "total_students": total_students,
        "present_count": present_count,
        "late_count": late_count,
        "absent_count": absent_count,
        "marked_count": marked_count,
        "not_marked_count": not_marked_count,
    }


# =========================================================
# ROSTER LOCK HELPER
# =========================================================
def build_attendance_history_locked(student, record=None):
    """
    Return one official boolean for roster removal lock state.

    Teaching idea:
    The template should not need to guess several different names.

    So here I normalize possible backend/model indicators into one stable field:
    attendance_history_locked

    Safety:
    I use getattr with defaults because different project stages may expose
    different attribute names, and I do not want the page to crash.
    """
    candidate_values = [
        getattr(record, "attendance_history_locked", False) if record else False,
        getattr(record, "has_locked_history_indicator", False) if record else False,
        getattr(record, "has_locked_attendance_history", False) if record else False,
        getattr(record, "locked_history_indicator", False) if record else False,
        getattr(record, "is_history_locked", False) if record else False,
        getattr(record, "remove_locked", False) if record else False,

        getattr(student, "attendance_history_locked", False),
        getattr(student, "has_locked_history_indicator", False),
        getattr(student, "has_locked_attendance_history", False),
        getattr(student, "locked_history_indicator", False),
        getattr(student, "is_history_locked", False),
        getattr(student, "remove_locked", False),
    ]

    return any(bool(value) for value in candidate_values)


# =========================================================
# ANALYTICS HELPERS
# =========================================================
def calculate_percentage(part, total):
    """
    Small safe percentage helper.

    Why I use this:
    I never want division-by-zero errors inside analytics pages.
    """
    if total <= 0:
        return 0.0

    return round((part / total) * 100, 2)


def build_session_analytics(total_students, records):
    """
    Build one clean analytics package for a single session.

    This helps the analytics template show:
    - present %
    - late %
    - absent %
    - marked %
    - unmarked %
    - card values
    """
    summary = build_attendance_summary(total_students, records)

    analytics = {
        "summary": summary,
        "present_percentage": calculate_percentage(
            summary["present_count"],
            total_students
        ),
        "late_percentage": calculate_percentage(
            summary["late_count"],
            total_students
        ),
        "absent_percentage": calculate_percentage(
            summary["absent_count"],
            total_students
        ),
        "marked_percentage": calculate_percentage(
            summary["marked_count"],
            total_students
        ),
        "not_marked_percentage": calculate_percentage(
            summary["not_marked_count"],
            total_students
        ),
    }

    return analytics


def build_session_trend_items(class_group_id, limit=8):
    """
    Build trend data using recent sessions from the same class group.

    I use this for small charts/cards later in the frontend.
    """
    all_teacher_sessions = get_sessions_by_teacher(current_user.id)

    class_sessions = [
        session for session in all_teacher_sessions
        if session.class_group_id == class_group_id
    ]

    class_sessions = sorted(
        class_sessions,
        key=lambda session: session.start_time or datetime.min,
        reverse=True
    )

    recent_sessions = class_sessions[:limit]
    trend_items = []

    for session in recent_sessions:
        total_students = len(get_active_students_by_class(session.class_group_id))
        records = get_attendance_records_by_session(session.id)
        analytics = build_session_analytics(total_students, records)

        session_label = "No date"

        if session.start_time:
            session_label = session.start_time.strftime("%Y-%m-%d")

        trend_items.append({
            "session_id": session.id,
            "session_label": session_label,
            "present_percentage": analytics["present_percentage"],
            "late_percentage": analytics["late_percentage"],
            "absent_percentage": analytics["absent_percentage"],
            "marked_percentage": analytics["marked_percentage"],
            "total_students": analytics["summary"]["total_students"],
            "present_count": analytics["summary"]["present_count"],
            "late_count": analytics["summary"]["late_count"],
            "absent_count": analytics["summary"]["absent_count"],
            "not_marked_count": analytics["summary"]["not_marked_count"],
            "is_open": session.is_open,
        })

    trend_items.reverse()
    return trend_items


def build_teacher_overall_class_snapshot(class_group_id):
    """
    Build one higher-level summary for the class analytics page.
    """
    trend_items = build_session_trend_items(class_group_id, limit=12)

    if not trend_items:
        return {
            "total_sessions": 0,
            "average_present_percentage": 0.0,
            "best_present_percentage": 0.0,
            "lowest_present_percentage": 0.0,
        }

    present_percentages = [
        item["present_percentage"]
        for item in trend_items
    ]

    average_present_percentage = round(
        sum(present_percentages) / len(present_percentages),
        2
    )

    return {
        "total_sessions": len(trend_items),
        "average_present_percentage": average_present_percentage,
        "best_present_percentage": max(present_percentages),
        "lowest_present_percentage": min(present_percentages),
    }


# =========================================================
# PAGINATION
# =========================================================
def paginate_items(items, page=1, per_page=5):
    """
    Small in-memory pagination helper.
    """
    total_items = len(items)

    if per_page <= 0:
        per_page = 5

    total_pages = ceil(total_items / per_page) if total_items > 0 else 1

    if page < 1:
        page = 1

    if page > total_pages:
        page = total_pages

    start_index = (page - 1) * per_page
    end_index = start_index + per_page

    paginated_items = items[start_index:end_index]

    pagination = {
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < total_pages else None,
        "start_index": start_index + 1 if total_items > 0 else 0,
        "end_index": min(end_index, total_items),
    }

    return paginated_items, pagination


# =========================================================
# OWNERSHIP HELPERS
# =========================================================
def teacher_owns_class_group(class_group_id):
    """
    Check that the class belongs to the logged-in teacher.
    """
    teacher_classes = get_teacher_class_groups(current_user.id)
    return any(class_group.id == class_group_id for class_group in teacher_classes)


def teacher_owns_session(session):
    """
    Check that the session belongs to the logged-in teacher.
    """
    if not session:
        return False

    if not session.class_group:
        return False

    return session.class_group.teacher_id == current_user.id


def get_teacher_owned_class_group_or_none(class_group_id):
    """
    Return one class group only if it belongs to the current teacher.
    """
    teacher_classes = get_teacher_class_groups(current_user.id)

    for class_group in teacher_classes:
        if class_group.id == class_group_id:
            return class_group

    return None


def build_open_session_form_context(class_group, notes="", error_message=""):
    """
    Build one stable context package for the open-session form page.
    """
    total_students = len(get_active_students_by_class(class_group.id))

    return {
        "page_title": "Open Session",
        "teacher_name": current_user.full_name(),
        "class_group": class_group,
        "notes_value": notes,
        "error_message": error_message,
        "total_students": total_students,
    }


# =========================================================
# DASHBOARD
# =========================================================
@docente_views_bp.route("/docente/dashboard")
@login_required
def docente_dashboard_page():
    """
    Main teacher dashboard page.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    class_groups = get_teacher_class_groups(current_user.id)
    sessions = get_sessions_by_teacher(current_user.id)

    dashboard_items = []

    for class_group in class_groups:
        class_sessions = [session for session in sessions if session.class_group_id == class_group.id]

        open_session = next((session for session in class_sessions if session.is_open), None)

        sorted_sessions = sorted(
            class_sessions,
            key=lambda session: session.start_time or datetime.min,
            reverse=True
        )
        last_session = sorted_sessions[0] if sorted_sessions else None

        target_session = open_session if open_session else last_session
        total_students = len(get_active_students_by_class(class_group.id))

        if target_session:
            records = get_attendance_records_by_session(target_session.id)
            summary = build_attendance_summary(total_students, records)
        else:
            summary = {
                "total_students": total_students,
                "present_count": 0,
                "late_count": 0,
                "absent_count": 0,
                "marked_count": 0,
                "not_marked_count": total_students,
            }

        dashboard_items.append({
            "class_group": class_group,
            "open_session": open_session,
            "last_session": last_session,
            "attendance_summary": summary,
        })

    return render_template(
        "docente/docente_dashboard.html",
        page_title="Teacher Dashboard",
        teacher_name=current_user.full_name(),
        dashboard_items=dashboard_items,
    )


# =========================================================
# CLASSES PAGE
# =========================================================
@docente_views_bp.route("/docente/classes")
@login_required
def docente_classes_page():
    """
    Teacher classes page.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    class_groups = get_teacher_class_groups(current_user.id)
    sessions = get_sessions_by_teacher(current_user.id)

    class_items = []

    for class_group in class_groups:
        class_sessions = [session for session in sessions if session.class_group_id == class_group.id]

        open_session = next((session for session in class_sessions if session.is_open), None)

        sorted_sessions = sorted(
            class_sessions,
            key=lambda session: session.start_time or datetime.min,
            reverse=True
        )
        last_session = sorted_sessions[0] if sorted_sessions else None

        target_session = open_session if open_session else last_session
        students = get_active_students_by_class(class_group.id)
        total_students = len(students)

        if target_session:
            records = get_attendance_records_by_session(target_session.id)
            summary = build_attendance_summary(total_students, records)
        else:
            summary = {
                "total_students": total_students,
                "present_count": 0,
                "late_count": 0,
                "absent_count": 0,
                "marked_count": 0,
                "not_marked_count": total_students,
            }

        class_items.append({
            "class_group": class_group,
            "open_session": open_session,
            "last_session": last_session,
            "attendance_summary": summary,
            "students_count": total_students,
            "students": students,
        })

    return render_template(
        "docente/docente_classes.html",
        page_title="My Classes",
        teacher_name=current_user.full_name(),
        class_items=class_items,
    )


# =========================================================
# SAFE ROSTER REDIRECT
# =========================================================
@docente_views_bp.route("/docente/session/<int:session_id>/roster-page")
@login_required
def docente_roster_redirect(session_id):
    """
    Safer route used by dashboard/classes buttons before entering roster page.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    session = get_class_session_by_id(session_id)

    if not session:
        return redirect("/docente/dashboard")

    if not teacher_owns_session(session):
        return redirect("/docente/dashboard")

    return redirect(f"/docente/attendance/session/{session_id}/roster")


# =========================================================
# SESSION ANALYTICS PAGE
# =========================================================
@docente_views_bp.route("/docente/session/<int:session_id>/analytics")
@login_required
def docente_session_analytics_page(session_id):
    """
    Professional teacher analytics page for one session.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    session = get_class_session_by_id(session_id)

    if not session:
        return redirect("/docente/sessions/history")

    if not teacher_owns_session(session):
        return redirect("/docente/dashboard")

    class_group = session.class_group
    total_students = len(get_active_students_by_class(class_group.id))
    records = get_attendance_records_by_session(session.id)

    session_analytics = build_session_analytics(total_students, records)
    trend_items = build_session_trend_items(class_group.id, limit=8)
    class_snapshot = build_teacher_overall_class_snapshot(class_group.id)

    return render_template(
        "docente/docente_session_analytics.html",
        page_title="Session Analytics",
        teacher_name=current_user.full_name(),
        session=session,
        class_group=class_group,
        analytics=session_analytics,
        trend_items=trend_items,
        class_snapshot=class_snapshot,
    )


# =========================================================
# SESSION HISTORY
# =========================================================
@docente_views_bp.route("/docente/sessions/history")
@login_required
def docente_session_history_page():
    """
    Teacher session history with real UI filters + pagination.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    subject = request.args.get("subject")
    status = request.args.get("status")
    from_date_str = request.args.get("from_date")
    to_date_str = request.args.get("to_date")

    raw_page = request.args.get("page", 1)
    raw_per_page = request.args.get("per_page", 5)

    try:
        page = int(raw_page)
    except Exception:
        page = 1

    try:
        per_page = int(raw_per_page)
    except Exception:
        per_page = 5

    from_date = None
    to_date = None

    try:
        if from_date_str:
            from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
    except Exception:
        from_date = None

    try:
        if to_date_str:
            to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
    except Exception:
        to_date = None

    sessions = get_sessions_by_teacher(
        current_user.id,
        search=subject,
        status=status,
        session_date=None,
    )

    if from_date or to_date:
        filtered_sessions = []

        for session in sessions:
            if not session.start_time:
                continue

            session_day = session.start_time.date()

            if from_date and session_day < from_date:
                continue

            if to_date and session_day > to_date:
                continue

            filtered_sessions.append(session)

        sessions = filtered_sessions

    history_items = []

    for session in sessions:
        total_students = len(get_active_students_by_class(session.class_group_id))
        records = get_attendance_records_by_session(session.id)
        summary = build_attendance_summary(total_students, records)

        history_items.append({
            "session": session,
            "class_group": session.class_group,
            "summary": summary,
        })

    history_items.sort(
        key=lambda item: item["session"].start_time or datetime.min,
        reverse=True,
    )

    history_items, pagination = paginate_items(
        history_items,
        page=page,
        per_page=per_page,
    )

    return render_template(
        "docente/docente_session_history.html",
        page_title="Session History",
        teacher_name=current_user.full_name(),
        history_items=history_items,
        pagination=pagination,
    )


# =========================================================
# EXPORT CENTER PAGE
# =========================================================
@docente_views_bp.route("/docente/export-center")
@login_required
def docente_export_center_page():
    """
    Professional teacher export dashboard page.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    return render_template(
        "docente/docente_export_center.html",
        page_title="Export Center",
        teacher_name=current_user.full_name(),
        current_subject=request.args.get("subject", ""),
        current_status=request.args.get("status", ""),
        current_from_date=request.args.get("from_date", ""),
        current_to_date=request.args.get("to_date", ""),
    )


# =========================================================
# EXPORT FILTERED SESSIONS CSV
# =========================================================
@docente_views_bp.route("/docente/export/sessions/csv")
@login_required
def docente_export_filtered_sessions_csv():
    """
    Professional academic export route.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    subject = request.args.get("subject")
    status = request.args.get("status")
    from_date_str = request.args.get("from_date")
    to_date_str = request.args.get("to_date")

    from_date = None
    to_date = None

    try:
        if from_date_str:
            from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
    except Exception:
        from_date = None

    try:
        if to_date_str:
            to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
    except Exception:
        to_date = None

    sessions = get_sessions_by_teacher(
        current_user.id,
        search=subject,
        status=status,
        session_date=None,
    )

    if from_date or to_date:
        filtered = []

        for session in sessions:
            if not session.start_time:
                continue

            session_day = session.start_time.date()

            if from_date and session_day < from_date:
                continue

            if to_date and session_day > to_date:
                continue

            filtered.append(session)

        sessions = filtered

    sessions = sorted(
        sessions,
        key=lambda session: session.start_time or datetime.min,
        reverse=True
    )

    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)

    writer.writerow([
        "Session ID",
        "Subject",
        "Status",
        "Start",
        "End",
        "Total Students",
        "Present",
        "Late",
        "Absent",
        "Not Marked"
    ])

    for session in sessions:
        total_students = len(get_active_students_by_class(session.class_group_id))
        records = get_attendance_records_by_session(session.id)
        summary = build_attendance_summary(total_students, records)

        writer.writerow([
            session.id,
            session.class_group.subject_name if session.class_group else "Unknown",
            "Open" if session.is_open else "Closed",
            session.start_time,
            session.end_time,
            summary["total_students"],
            summary["present_count"],
            summary["late_count"],
            summary["absent_count"],
            summary["not_marked_count"],
        ])

    csv_buffer.seek(0)

    file_date = datetime.utcnow().date()

    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            f"attachment; filename=teacher_sessions_export_{file_date}.csv"
        }
    )


# =========================================================
# OPEN SESSION FORM PAGE
# =========================================================
@docente_views_bp.route("/docente/class/<int:class_group_id>/open-session-form")
@login_required
def docente_open_session_form_page(class_group_id):
    """
    Show the open-session form page.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    class_group = get_teacher_owned_class_group_or_none(class_group_id)

    if not class_group:
        return redirect("/docente/dashboard")

    return render_template(
        "docente/docente_open_session.html",
        **build_open_session_form_context(class_group=class_group)
    )


# =========================================================
# ACTION ROUTES
# =========================================================
@docente_views_bp.route("/docente/class/<int:class_group_id>/open-session", methods=["POST"])
@login_required
def docente_open_session_action(class_group_id):
    """
    Open a new class session from the dedicated form page.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    class_group = get_teacher_owned_class_group_or_none(class_group_id)

    if not class_group:
        return redirect("/docente/dashboard")

    notes = (request.form.get("notes") or "").strip()

    if len(notes) > 500:
        return render_template(
            "docente/docente_open_session.html",
            **build_open_session_form_context(
                class_group=class_group,
                notes=notes,
                error_message="Notes cannot be longer than 500 characters."
            )
        )

    if not notes:
        notes = None

    try:
        session = create_class_session(
            class_group_id=class_group_id,
            teacher_id=current_user.id,
            notes=notes
        )
    except ValueError as error:
        return render_template(
            "docente/docente_open_session.html",
            **build_open_session_form_context(
                class_group=class_group,
                notes=notes or "",
                error_message=str(error)
            )
        )
    except Exception:
        return render_template(
            "docente/docente_open_session.html",
            **build_open_session_form_context(
                class_group=class_group,
                notes=notes or "",
                error_message="An unexpected error occurred while opening the session."
            )
        )

    return redirect(f"/docente/session/{session.id}/roster-page")


@docente_views_bp.route("/docente/session/<int:session_id>/close", methods=["POST"])
@login_required
def docente_close_session_action(session_id):
    """
    Close one class session and return to dashboard.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    session = get_class_session_by_id(session_id)

    if not teacher_owns_session(session):
        return redirect("/docente/dashboard")

    try:
        close_class_session(session_id, current_user.id)
    except Exception:
        pass

    return redirect("/docente/dashboard")


@docente_views_bp.route("/docente/session/<int:session_id>/reopen", methods=["POST"])
@login_required
def docente_reopen_session_action(session_id):
    """
    Reopen one class session and return to dashboard.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    session = get_class_session_by_id(session_id)

    if not teacher_owns_session(session):
        return redirect("/docente/dashboard")

    try:
        reopen_class_session(session_id, current_user.id)
    except Exception:
        pass

    return redirect("/docente/dashboard")


# =========================================================
# ROSTER PAGE
# =========================================================
@docente_views_bp.route("/docente/attendance/session/<int:session_id>/roster")
@login_required
def docente_roster_page(session_id):
    """
    Teacher roster / attendance page for one session.
    """
    if not docente_page_guard():
        return redirect("/auth/login-page")

    session = get_class_session_by_id(session_id)

    if not session:
        return render_template(
            "docente/docente_roster.html",
            page_title="Class Roster Attendance",
            teacher_name=current_user.full_name(),
            session=None,
            class_group=None,
            summary={
                "total_students": 0,
                "present_count": 0,
                "late_count": 0,
                "absent_count": 0,
                "marked_count": 0,
                "not_marked_count": 0,
            },
            roster=[],
        )

    if not teacher_owns_session(session):
        return redirect("/docente/dashboard")

    class_group = session.class_group
    students = get_active_students_by_class(class_group.id)
    records = get_attendance_records_by_session(session.id)

    records_by_student_id = {
        record.student_id: record
        for record in records
    }

    roster = []

    for student in students:
        record = records_by_student_id.get(student.id)
        attendance_history_locked = build_attendance_history_locked(
            student=student,
            record=record,
        )

        roster.append({
            "student_id": student.id,
            "student_name": student.full_name(),
            "student_username": student.username,
            "student_email": student.email,
            "attendance_status": record.status if record else "not_marked",
            "notes": record.notes if record else "",
            "attendance_history_locked": attendance_history_locked,
        })

    summary = build_attendance_summary(len(students), records)

    return render_template(
        "docente/docente_roster.html",
        page_title="Class Roster Attendance",
        teacher_name=current_user.full_name(),
        session=session,
        class_group=class_group,
        summary=summary,
        roster=roster,
    )