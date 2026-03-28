"""
user_model.py

Professional User model for UniTrack.

This model supports:
- role based access
- admin system
- docente class ownership
- teacher class session ownership
- student class enrollment
- student attendance receiving
- account activation
- login tracking
- user language preference

Important architecture update:
Attendance is no longer treated as an admin feature.

Now the system is moving toward:
- teacher owns class groups
- teacher opens class sessions
- students are enrolled into class groups
- students receive attendance results inside those sessions
"""

from datetime import datetime
from flask_login import UserMixin

from app.database import db


class User(UserMixin, db.Model):
    """
    User table for UniTrack.

    This table stores the main identity and security data
    for each system account.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # Identity
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)

    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)

    phone = db.Column(db.String(20), nullable=False)

    # User preference
    # Current allowed values:
    # - en = English
    # - es = Español
    language = db.Column(
        db.String(10),
        nullable=False,
        default="en"
    )

    # Security
    password_hash = db.Column(db.String(255), nullable=False)

    # Role system
    role = db.Column(
        db.String(30),
        nullable=False,
        default="estudiante",
        index=True
    )

    # Account state
    must_change_password = db.Column(db.Boolean, default=False)
    is_active_user = db.Column(db.Boolean, default=True)

    # Optional profile photo
    photo_path = db.Column(db.String(255), nullable=True)

    # Login tracking
    last_login_at = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Teacher -> many class groups
    # Teaching idea:
    # One docente can manage many groups/classes.
    teaching_classes = db.relationship(
        "ClassGroup",
        backref="teacher",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # Teacher -> many class sessions
    # Teaching idea:
    # A docente does not directly mark attendance rows anymore.
    # First, the docente opens a class session.
    # Then student attendance is saved inside that session.
    teaching_sessions = db.relationship(
        "ClassSession",
        foreign_keys="ClassSession.teacher_id",
        backref="teacher_user",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # Student -> many class enrollments
    # Teaching idea:
    # A student can belong to many classes.
    # We do not store that directly in the user table.
    # Instead, we use the ClassEnrollment table as a bridge.
    student_class_enrollments = db.relationship(
        "ClassEnrollment",
        foreign_keys="ClassEnrollment.student_id",
        back_populates="student",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # Student -> many attendance records
    # Teaching idea:
    # This lets the system load all attendance results
    # that belong to one student across sessions/classes.
    student_attendance_records = db.relationship(
        "Attendance",
        foreign_keys="Attendance.student_id",
        backref="student",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def full_name(self):
        """
        Return full name in one clean string.
        """
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        """
        Helpful for debugging in terminal.
        """
        return f"<User {self.username} ({self.role})>"