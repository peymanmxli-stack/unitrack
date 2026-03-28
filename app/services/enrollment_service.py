"""
enrollment_service.py

Professional enrollment service layer for UniTrack.

Teaching idea:
Routes should NOT directly contain database logic.

Instead:

Route
    -> calls service
Service
    -> validates business rules
    -> talks to database
    -> returns clean result

This file manages the relationship between:
- class groups
- students
- enrollments
"""

from app.database import db
from app.models.user_model import User
from app.models.class_group_model import ClassGroup
from app.models.class_enrollment_model import ClassEnrollment
from app.models.class_session_model import ClassSession
from app.models.attendance_model import Attendance


def get_class_by_id(class_group_id):
    """
    Get one class group by its ID.
    """
    return ClassGroup.query.get(class_group_id)


def get_student_by_id(student_id):
    """
    Get one student user by ID.
    """
    return User.query.get(student_id)


def get_enrollment_by_class_and_student(class_group_id, student_id):
    """
    Find one enrollment record by class and student.

    This helps us prevent duplicate enrollments.
    """
    return ClassEnrollment.query.filter_by(
        class_group_id=class_group_id,
        student_id=student_id
    ).first()


def class_has_attendance_for_student(class_group_id, student_id):
    """
    Check whether this student already has attendance records
    in any session that belongs to the class.

    Why this protection matters:
    If attendance already exists, removing the student from the class
    can break historical class/session consistency.
    """
    return db.session.query(Attendance.id).join(
        ClassSession,
        Attendance.class_session_id == ClassSession.id
    ).filter(
        ClassSession.class_group_id == class_group_id,
        Attendance.student_id == student_id
    ).first() is not None


def enroll_student_in_class(class_group_id, student_id, notes=None):
    """
    Enroll one student into one class.

    Business rules:
    - class must exist
    - student must exist
    - student role should be 'estudiante'
    - duplicate active enrollment should not be allowed
    """
    class_group = get_class_by_id(class_group_id)
    if not class_group:
        raise ValueError("Class group not found")

    student = get_student_by_id(student_id)
    if not student:
        raise ValueError("Student not found")

    if student.role != "estudiante":
        raise ValueError("Only users with role 'estudiante' can be enrolled")

    existing_enrollment = get_enrollment_by_class_and_student(
        class_group_id,
        student_id
    )

    # If already actively enrolled, block duplicate creation
    if existing_enrollment and existing_enrollment.is_active:
        raise ValueError("This student is already enrolled in this class.")

    # If enrollment existed before but was deactivated,
    # we reactivate it instead of creating duplicate rows.
    if existing_enrollment and not existing_enrollment.is_active:
        existing_enrollment.is_active = True
        existing_enrollment.notes = notes
        db.session.commit()
        return existing_enrollment

    enrollment = ClassEnrollment(
        class_group_id=class_group_id,
        student_id=student_id,
        notes=notes
    )

    db.session.add(enrollment)
    db.session.commit()

    return enrollment


def get_enrollments_by_class(class_group_id, active_only=True):
    """
    Return enrollment rows for one class.

    By default we return only active students,
    because that is what a teacher normally needs
    for attendance and roster views.
    """
    query = ClassEnrollment.query.filter_by(class_group_id=class_group_id)

    if active_only:
        query = query.filter_by(is_active=True)

    return query.order_by(ClassEnrollment.joined_at.asc()).all()


def get_active_students_by_class(class_group_id):
    """
    Helper for roster screens.

    IMPORTANT:
    The docente roster UI needs REAL student User objects,
    not enrollment rows.

    So this helper:
    1. loads active enrollment rows
    2. extracts each related student user
    3. returns a clean list of User objects
    """
    enrollments = get_enrollments_by_class(
        class_group_id=class_group_id,
        active_only=True
    )

    students = []

    for enrollment in enrollments:
        if enrollment.student:
            students.append(enrollment.student)

    return students


def remove_student_from_class(class_group_id, student_id):
    """
    Soft remove a student from a class.

    Important:
    We do NOT delete the row immediately.

    Why?
    Because later the university may want history like:
    - who used to belong to this class
    - when they were enrolled
    - attendance audit trail
    """
    enrollment = get_enrollment_by_class_and_student(class_group_id, student_id)

    if not enrollment:
        raise ValueError("Enrollment not found")

    if not enrollment.is_active:
        raise ValueError("Student is already removed from this class")

    if class_has_attendance_for_student(class_group_id, student_id):
        raise ValueError(
            "This student cannot be removed because attendance records already exist."
        )

    enrollment.is_active = False
    db.session.commit()

    return enrollment