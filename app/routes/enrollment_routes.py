"""
enrollment_routes.py

Enrollment routes for UniTrack.

Teaching idea:
This file exposes backend API endpoints for:

- adding a student into a class
- listing the students of a class
- removing a student from a class

Important architecture note:
Enrollment is the bridge between:

ClassGroup <-> Student

This makes roster-based attendance possible.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.models.class_group_model import ClassGroup
from app.services.enrollment_service import (
    enroll_student_in_class,
    get_active_students_by_class,
    remove_student_from_class
)

enrollment_bp = Blueprint(
    "enrollment",
    __name__,
    url_prefix="/enrollment"
)


def serialize_enrollment(enrollment):
    """
    Convert one enrollment row into clean JSON.

    This is useful for frontend roster tables.
    """
    return {
        "enrollment_id": enrollment.id,
        "class_group_id": enrollment.class_group_id,
        "student_id": enrollment.student_id,
        "student_name": f"{enrollment.student.first_name} {enrollment.student.last_name}",
        "student_username": enrollment.student.username,
        "student_email": enrollment.student.email,
        "student_role": enrollment.student.role,
        "is_active": enrollment.is_active,
        "joined_at": enrollment.joined_at.isoformat() if enrollment.joined_at else None,
        "notes": enrollment.notes
    }


def user_can_manage_class(class_group):
    """
    Permission helper.

    Rules:
    - administrativo can manage any class
    - docente can only manage their own class

    Important UniTrack rule:
    The real admin role in this project is "administrativo",
    not "admin".
    """
    if current_user.role == "administrativo":
        return True

    if current_user.role == "docente" and class_group.teacher_id == current_user.id:
        return True

    return False


@enrollment_bp.route("/classes/<int:class_group_id>/students", methods=["POST"])
@login_required
def enroll_student(class_group_id):
    """
    Enroll one student into one class.

    Expected JSON:
    {
        "student_id": 3,
        "notes": "Optional text"
    }
    """
    class_group = ClassGroup.query.get(class_group_id)

    if not class_group:
        return jsonify({
            "success": False,
            "error": "Class group not found"
        }), 404

    if not user_can_manage_class(class_group):
        return jsonify({
            "success": False,
            "error": "You do not have permission to manage this class"
        }), 403

    data = request.get_json() or {}

    student_id = data.get("student_id")
    notes = data.get("notes")

    if not student_id:
        return jsonify({
            "success": False,
            "error": "student_id is required"
        }), 400

    try:
        enrollment = enroll_student_in_class(
            class_group_id=class_group_id,
            student_id=student_id,
            notes=notes
        )

        return jsonify({
            "success": True,
            "message": "Student enrolled successfully",
            "enrollment": serialize_enrollment(enrollment)
        }), 201

    except ValueError as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 400


@enrollment_bp.route("/classes/<int:class_group_id>/students", methods=["GET"])
@login_required
def get_class_roster(class_group_id):
    """
    Get active roster for one class.

    This is what the frontend will use later to show:
    - who belongs to the class
    - who can be marked present/absent
    """
    class_group = ClassGroup.query.get(class_group_id)

    if not class_group:
        return jsonify({
            "success": False,
            "error": "Class group not found"
        }), 404

    if not user_can_manage_class(class_group):
        return jsonify({
            "success": False,
            "error": "You do not have permission to view this class roster"
        }), 403

    enrollments = get_active_students_by_class(class_group_id)

    return jsonify({
        "success": True,
        "class_group": {
            "id": class_group.id,
            "subject_name": class_group.subject_name,
            "group_code": class_group.group_code,
            "display_name": class_group.class_display_name()
        },
        "total_students": len(enrollments),
        "students": [serialize_enrollment(enrollment) for enrollment in enrollments]
    }), 200


@enrollment_bp.route("/classes/<int:class_group_id>/students/<int:student_id>", methods=["POST"])
@login_required
def remove_student(class_group_id, student_id):
    """
    Soft remove one student from a class.

    Important:
    We use POST here for simplicity in your current project flow.

    Later, if you want, we can change it to:
    DELETE /classes/<id>/students/<id>
    """
    class_group = ClassGroup.query.get(class_group_id)

    if not class_group:
        return jsonify({
            "success": False,
            "error": "Class group not found"
        }), 404

    if not user_can_manage_class(class_group):
        return jsonify({
            "success": False,
            "error": "You do not have permission to manage this class"
        }), 403

    try:
        enrollment = remove_student_from_class(class_group_id, student_id)

        return jsonify({
            "success": True,
            "message": "Student removed from class successfully",
            "enrollment": serialize_enrollment(enrollment)
        }), 200

    except ValueError as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 400