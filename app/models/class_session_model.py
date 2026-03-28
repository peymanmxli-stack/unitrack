"""
class_session_model.py

Professional Class Session model for UniTrack.

Teaching idea:
A class group is the academic container,
but a class session is one REAL meeting of that class.

Example:

ClassGroup:
- Databases 3AFM

ClassSession:
- Databases 3AFM
- 2026-03-24
- 08:00 AM to 10:00 AM
- opened by teacher Peyman

Why this model is important:
Real attendance should not be attached only to a date.

It should be attached to a REAL class session.

This allows the system to support:
- multiple sessions in one day
- makeup sessions
- extra sessions
- cancelled sessions later
- session notes
- more professional teacher workflow

Architecture:
ClassGroup -> ClassSession -> Attendance
"""

from datetime import datetime

from app.database import db


class ClassSession(db.Model):
    """
    ClassSession = one real class meeting.

    This model answers:
    - which class was opened
    - which teacher opened it
    - on what date
    - what time it started
    - what time it ended
    - whether it is still active/open
    """

    __tablename__ = "class_sessions"

    id = db.Column(db.Integer, primary_key=True)

    # Which academic group this session belongs to
    class_group_id = db.Column(
        db.Integer,
        db.ForeignKey("class_groups.id"),
        nullable=False,
        index=True
    )

    # Which teacher opened this session
    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Academic session date
    session_date = db.Column(
        db.Date,
        nullable=False,
        index=True,
        default=lambda: datetime.utcnow().date()
    )

    # Optional time range
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)

    # Optional teacher notes
    # Example:
    # "Lab session"
    # "Short quiz today"
    # "Makeup class due to holiday"
    notes = db.Column(db.String(255), nullable=True)

    # Helps teacher workflow.
    # Example:
    # session is opened -> marking happens
    # session is closed -> attendance finished
    is_open = db.Column(db.Boolean, nullable=False, default=True, index=True)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationship:
    # one class session -> many attendance rows
    attendance_records = db.relationship(
        "Attendance",
        backref="class_session",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<ClassSession ClassGroup:{self.class_group_id} "
            f"Teacher:{self.teacher_id} "
            f"Date:{self.session_date} "
            f"Open:{self.is_open}>"
        )