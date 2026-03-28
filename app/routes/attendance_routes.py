"""
attendance_routes.py

Professional docente attendance routes for UniTrack.

NEW ARCHITECTURE:
Attendance is no longer a personal check-in / check-out system.

Now attendance belongs to the docente workflow:

Teacher
    -> loads their classes
    -> opens one class session
    -> loads enrolled roster from that class
    -> marks students present/absent
    -> reviews attendance for that session
    -> closes the session
    -> can reopen a closed session if correction is needed
    -> exports attendance report when needed

Teaching idea:
This file is the bridge between:
Frontend -> Route -> Service -> Database
"""

import csv
import io

from flask import Blueprint, jsonify, request, Response
from flask_login import login_required, current_user

from app.services.attendance_service import (
    get_teacher_class_groups,
    create_class_session,
    close_class_session,
    reopen_class_session,
    get_class_session_by_id,
    get_attendance_records_by_session,
    mark_student_attendance,
    mark_bulk_attendance,
    get_sessions_by_teacher
)
from app.services.enrollment_service import get_active_students_by_class

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


def serialize_class_group(class_group):
    """
    Convert one class group object into clean JSON.
    """
    return {
        "id": class_group.id,
        "subject_name": class_group.subject_name,
        "group_code": class_group.group_code,
        "description": class_group.description,
        "teacher_id": class_group.teacher_id,
        "is_active": class_group.is_active,
        "created_at": class_group.created_at.isoformat() if class_group.created_at else None,
        "updated_at": class_group.updated_at.isoformat() if class_group.updated_at else None,
        "display_name": class_group.class_display_name()
    }


def serialize_class_session(session):
    """
    Convert one class session object into clean JSON.
    """
    return {
        "id": session.id,
        "class_group_id": session.class_group_id,
        "teacher_id": session.teacher_id,
        "session_date": str(session.session_date),
        "start_time": session.start_time.isoformat() if session.start_time else None,
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "notes": session.notes,
        "is_open": session.is_open,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None
    }


def serialize_attendance_record(record):
    """
    Convert one attendance row into clean JSON.
    """
    return {
        "id": record.id,
        "session_id": record.session_id,
        "student_id": record.student_id,
        "student_name": record.student.full_name() if record.student else None,
        "student_username": record.student.username if record.student else None,
        "status": record.status,
        "notes": record.notes,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None
    }


def docente_only():
    """
    Small helper to protect teacher attendance endpoints.
    """
    if not current_user.is_active_user:
        return jsonify({
            "success": False,
            "error": "Your account is inactive"
        }), 403

    if current_user.role != "docente":
        return jsonify({
            "success": False,
            "error": "Only docentes can access attendance management"
        }), 403

    return None


def build_session_export_rows(session):
    """
    Build CSV-ready attendance export rows for one class session.

    Teaching idea:
    Export should not only include already-marked students.
    It should include the FULL active class roster, then match each student
    with the current attendance record if one exists.

    Important real-world fix:
    In this project, get_active_students_by_class() currently returns
    direct User student objects, not enrollment objects.

    So in this export builder I must treat each item as a student.
    That is why I should read:
    - student.id
    - student.full_name()
    - student.username
    - student.email

    and not use:
    - enrollment.student
    - enrollment.student_id
    - enrollment.joined_at
    """
    students = get_active_students_by_class(session.class_group_id)
    attendance_records = get_attendance_records_by_session(session.id)

    attendance_map = {
        record.student_id: record
        for record in attendance_records
    }

    export_rows = []

    for student in students:
        attendance_record = attendance_map.get(student.id)

        export_rows.append({
            "student_id": student.id,
            "student_name": student.full_name() if hasattr(student, "full_name") else "",
            "student_username": student.username if hasattr(student, "username") else "",
            "student_email": student.email if hasattr(student, "email") else "",
            "attendance_status": attendance_record.status if attendance_record else "not_marked",
            "attendance_notes": attendance_record.notes if attendance_record else "",
            "attendance_record_id": attendance_record.id if attendance_record else "",
            "attendance_created_at": (
                attendance_record.created_at.isoformat()
                if attendance_record and attendance_record.created_at else ""
            ),
            "attendance_updated_at": (
                attendance_record.updated_at.isoformat()
                if attendance_record and attendance_record.updated_at else ""
            ),

            # We do not have enrollment rows in this function right now,
            # so joined_at is left blank safely instead of crashing.
            "enrollment_joined_at": ""
        })

    return export_rows


def build_csv_filename_for_session(session):
    """
    Build a clean download filename for exported attendance.

    Example:
    attendance_math101_a_2026-03-24_session_12.csv
    """
    if session.class_group:
        subject_name = (session.class_group.subject_name or "class").strip().lower().replace(" ", "_")
        group_code = (session.class_group.group_code or "group").strip().lower().replace(" ", "_")
    else:
        subject_name = "class"
        group_code = "group"

    session_date = str(session.session_date) if session.session_date else "unknown_date"

    return f"attendance_{subject_name}_{group_code}_{session_date}_session_{session.id}.csv"


@attendance_bp.route("/classes", methods=["GET"])
@login_required
def get_my_classes():
    """
    Return all active classes that belong to the logged-in teacher.
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    class_groups = get_teacher_class_groups(current_user.id)

    return jsonify({
        "success": True,
        "total": len(class_groups),
        "classes": [serialize_class_group(class_group) for class_group in class_groups]
    })


@attendance_bp.route("/sessions", methods=["GET"])
@login_required
def get_my_sessions():
    """
    Return sessions that belong to the logged-in teacher.

    Optional query:
    /attendance/sessions?only_open=true
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    only_open_value = request.args.get("only_open", "false").strip().lower()
    only_open = only_open_value == "true"

    sessions = get_sessions_by_teacher(current_user.id, only_open=only_open)

    return jsonify({
        "success": True,
        "total": len(sessions),
        "sessions": [serialize_class_session(session) for session in sessions]
    })


@attendance_bp.route("/sessions/open", methods=["POST"])
@login_required
def open_class_session():
    """
    Open one new class session for a teacher-owned class.
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    data = request.get_json(silent=True) or {}

    class_group_id = data.get("class_group_id")
    notes = data.get("notes")

    if not class_group_id:
        return jsonify({
            "success": False,
            "error": "class_group_id is required"
        }), 400

    try:
        session = create_class_session(
            class_group_id=class_group_id,
            teacher_id=current_user.id,
            notes=notes
        )

        return jsonify({
            "success": True,
            "message": "Class session opened successfully",
            "session": serialize_class_session(session)
        }), 201

    except ValueError as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 400


@attendance_bp.route("/sessions/<int:session_id>", methods=["GET"])
@login_required
def get_one_session(session_id):
    """
    Return one teacher-owned class session.
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    session = get_class_session_by_id(session_id)

    if not session:
        return jsonify({
            "success": False,
            "error": "Class session not found"
        }), 404

    if session.teacher_id != current_user.id:
        return jsonify({
            "success": False,
            "error": "You do not own this class session"
        }), 403

    return jsonify({
        "success": True,
        "session": serialize_class_session(session)
    })


@attendance_bp.route("/sessions/<int:session_id>/roster", methods=["GET"])
@login_required
def get_session_roster(session_id):
    """
    Return enrolled active students for the class that owns this session.

    UI upgrade:
    This endpoint now also returns the current attendance status for each student
    if that student has already been marked in this session.

    Real frontend result:
    teacher opens session -> loads one roster -> sees who is present/absent/not marked
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    session = get_class_session_by_id(session_id)

    if not session:
        return jsonify({
            "success": False,
            "error": "Class session not found"
        }), 404

    if session.teacher_id != current_user.id:
        return jsonify({
            "success": False,
            "error": "You do not own this class session"
        }), 403

    students = get_active_students_by_class(session.class_group_id)
    attendance_records = get_attendance_records_by_session(session_id)

    attendance_map = {
        record.student_id: record
        for record in attendance_records
    }

    roster = []

    for student in students:
        attendance_record = attendance_map.get(student.id)

        roster.append({
            "student_id": student.id,
            "student_name": student.full_name() if hasattr(student, "full_name") else None,
            "student_username": student.username if hasattr(student, "username") else None,
            "student_email": student.email if hasattr(student, "email") else None,
            "attendance_status": (
                attendance_record.status
                if attendance_record else "not_marked"
            ),
            "attendance_notes": attendance_record.notes if attendance_record else None,
            "attendance_record_id": attendance_record.id if attendance_record else None,
            "is_marked": (
                attendance_record.status != "not_marked"
                if attendance_record else False
            )
        })

    return jsonify({
        "success": True,
        "session": serialize_class_session(session),
        "class_group": {
            "id": session.class_group.id,
            "subject_name": session.class_group.subject_name,
            "group_code": session.class_group.group_code,
            "display_name": session.class_group.class_display_name()
        },
        "total_students": len(roster),
        "roster": roster
    }), 200


@attendance_bp.route("/sessions/<int:session_id>/attendance", methods=["GET"])
@login_required
def get_session_attendance(session_id):
    """
    Return all attendance rows inside one teacher-owned session.
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    session = get_class_session_by_id(session_id)

    if not session:
        return jsonify({
            "success": False,
            "error": "Class session not found"
        }), 404

    if session.teacher_id != current_user.id:
        return jsonify({
            "success": False,
            "error": "You do not own this class session"
        }), 403

    records = get_attendance_records_by_session(session_id)

    return jsonify({
        "success": True,
        "total": len(records),
        "session": serialize_class_session(session),
        "attendance_records": [
            serialize_attendance_record(record)
            for record in records
        ]
    })


@attendance_bp.route("/sessions/<int:session_id>/attendance/summary", methods=["GET"])
@login_required
def get_session_attendance_summary(session_id):
    """
    Return classroom attendance summary for one session.
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    session = get_class_session_by_id(session_id)

    if not session:
        return jsonify({
            "success": False,
            "error": "Class session not found"
        }), 404

    if session.teacher_id != current_user.id:
        return jsonify({
            "success": False,
            "error": "You do not own this class session"
        }), 403

    students = get_active_students_by_class(session.class_group_id)
    records = get_attendance_records_by_session(session_id)

    present_count = sum(1 for record in records if record.status == "present")
    absent_count = sum(1 for record in records if record.status == "absent")
    marked_count = present_count + absent_count
    total_students = len(students)
    not_marked_count = total_students - marked_count

    if not_marked_count < 0:
        not_marked_count = 0

    return jsonify({
        "success": True,
        "session": serialize_class_session(session),
        "summary": {
            "total_students": total_students,
            "present_count": present_count,
            "absent_count": absent_count,
            "marked_count": marked_count,
            "not_marked_count": not_marked_count
        }
    }), 200


@attendance_bp.route("/sessions/<int:session_id>/attendance/mark", methods=["POST"])
@login_required
def mark_one_student(session_id):
    """
    Mark attendance for one student in one session.
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    data = request.get_json(silent=True) or {}

    student_id = data.get("student_id")
    status = data.get("status")
    notes = data.get("notes")

    if not student_id:
        return jsonify({
            "success": False,
            "error": "student_id is required"
        }), 400

    if not status:
        return jsonify({
            "success": False,
            "error": "status is required"
        }), 400

    try:
        record = mark_student_attendance(
            session_id=session_id,
            teacher_id=current_user.id,
            student_id=student_id,
            status=status,
            notes=notes
        )

        return jsonify({
            "success": True,
            "message": "Student attendance saved successfully",
            "attendance": serialize_attendance_record(record)
        }), 200

    except ValueError as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 400


@attendance_bp.route("/sessions/<int:session_id>/attendance/bulk", methods=["POST"])
@login_required
def mark_bulk_students(session_id):
    """
    Mark attendance for many students in one session.
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    data = request.get_json(silent=True) or {}
    attendance_items = data.get("attendance_items", [])

    if not isinstance(attendance_items, list) or not attendance_items:
        return jsonify({
            "success": False,
            "error": "attendance_items must be a non-empty list"
        }), 400

    try:
        records = mark_bulk_attendance(
            session_id=session_id,
            teacher_id=current_user.id,
            attendance_items=attendance_items
        )

        return jsonify({
            "success": True,
            "message": "Bulk attendance saved successfully",
            "total_saved": len(records),
            "attendance_records": [
                serialize_attendance_record(record)
                for record in records
            ]
        }), 200

    except ValueError as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 400


@attendance_bp.route("/sessions/<int:session_id>/reopen", methods=["POST"])
@login_required
def reopen_one_session(session_id):
    """
    Reopen one teacher-owned closed class session.

    Teaching idea:
    This gives the docente a safe correction workflow.
    If the teacher closed the session too early or needs to fix attendance,
    the session can be reopened, edited, and closed again.
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    try:
        session = reopen_class_session(
            session_id=session_id,
            teacher_id=current_user.id
        )

        return jsonify({
            "success": True,
            "message": "Class session reopened successfully",
            "session": serialize_class_session(session)
        }), 200

    except ValueError as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 400


@attendance_bp.route("/sessions/<int:session_id>/close", methods=["POST"])
@login_required
def close_one_session(session_id):
    """
    Close one teacher-owned class session.
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    try:
        session = close_class_session(
            session_id=session_id,
            teacher_id=current_user.id
        )

        return jsonify({
            "success": True,
            "message": "Class session closed successfully",
            "session": serialize_class_session(session)
        }), 200

    except ValueError as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 400


@attendance_bp.route("/sessions/<int:session_id>/export/csv", methods=["GET"])
@login_required
def export_session_attendance_csv(session_id):
    """
    Export one teacher-owned class session as CSV.

    Why CSV first:
    - simple
    - universal
    - opens in Excel, Google Sheets, LibreOffice
    - very common for attendance reports
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    session = get_class_session_by_id(session_id)

    if not session:
        return jsonify({
            "success": False,
            "error": "Class session not found"
        }), 404

    if session.teacher_id != current_user.id:
        return jsonify({
            "success": False,
            "error": "You do not own this class session"
        }), 403

    export_rows = build_session_export_rows(session)
    filename = build_csv_filename_for_session(session)

    output = io.StringIO()
    writer = csv.writer(output)

    # Report header section
    writer.writerow(["UniTrack Attendance Export"])
    writer.writerow(["Session ID", session.id])
    writer.writerow(["Session Date", session.session_date or ""])
    writer.writerow(["Session Open", "Yes" if session.is_open else "No"])
    writer.writerow(["Start Time", session.start_time.isoformat() if session.start_time else ""])
    writer.writerow(["End Time", session.end_time.isoformat() if session.end_time else ""])
    writer.writerow(["Teacher", current_user.full_name() if hasattr(current_user, "full_name") else current_user.username])
    writer.writerow(["Class", session.class_group.class_display_name() if session.class_group else ""])
    writer.writerow(["Subject", session.class_group.subject_name if session.class_group else ""])
    writer.writerow(["Group", session.class_group.group_code if session.class_group else ""])
    writer.writerow([])

    # Column header section
    writer.writerow([
        "student_id",
        "student_name",
        "student_username",
        "student_email",
        "attendance_status",
        "attendance_notes",
        "attendance_record_id",
        "attendance_created_at",
        "attendance_updated_at",
        "enrollment_joined_at"
    ])

    # Data rows
    for row in export_rows:
        writer.writerow([
            row["student_id"],
            row["student_name"],
            row["student_username"],
            row["student_email"],
            row["attendance_status"],
            row["attendance_notes"],
            row["attendance_record_id"],
            row["attendance_created_at"],
            row["attendance_updated_at"],
            row["enrollment_joined_at"]
        ])

    csv_content = output.getvalue()
    output.close()

    response = Response(
        csv_content,
        mimetype="text/csv; charset=utf-8"
    )

    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response


@attendance_bp.route("/dashboard", methods=["GET"])
@login_required
def docente_dashboard():
    """
    Single call teacher dashboard endpoint.

    Returns:
    - teacher classes
    - open session per class
    - attendance summary per class
    """
    teacher_block = docente_only()
    if teacher_block:
        return teacher_block

    class_groups = get_teacher_class_groups(current_user.id)
    teacher_sessions = get_sessions_by_teacher(current_user.id)

    open_sessions_by_class = {
        session.class_group_id: session
        for session in teacher_sessions
        if session.is_open
    }

    dashboard_items = []

    for class_group in class_groups:
        open_session = open_sessions_by_class.get(class_group.id)
        summary = None

        if open_session:
            students = get_active_students_by_class(class_group.id)
            records = get_attendance_records_by_session(open_session.id)

            present_count = sum(1 for record in records if record.status == "present")
            absent_count = sum(1 for record in records if record.status == "absent")
            marked_count = present_count + absent_count
            total_students = len(students)
            not_marked_count = total_students - marked_count

            if not_marked_count < 0:
                not_marked_count = 0

            summary = {
                "total_students": total_students,
                "present_count": present_count,
                "absent_count": absent_count,
                "marked_count": marked_count,
                "not_marked_count": not_marked_count
            }

        dashboard_items.append({
            "class": serialize_class_group(class_group),
            "open_session": serialize_class_session(open_session) if open_session else None,
            "attendance_summary": summary
        })

    return jsonify({
        "success": True,
        "total_classes": len(dashboard_items),
        "dashboard": dashboard_items
    }), 200