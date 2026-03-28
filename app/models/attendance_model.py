"""
attendance_model.py

Professional attendance record model for UniTrack.

NEW ARCHITECTURE:
Attendance is now session-based.

That means:
- ClassGroup = the academic class
- ClassSession = one real meeting of that class
- Attendance = one student's result inside that session

This is much stronger than old date-only attendance.

Why?
Because a class may have:
- normal session
- extra session
- makeup session
- more than one session in one day

So attendance should belong to a REAL session.

One row = one student attendance result in one class session.
"""

from datetime import datetime

from app.database import db


class Attendance(db.Model):
    """
    Attendance record for one student in one class session.
    """

    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)

    # Which class session this attendance belongs to
    session_id = db.Column(
        db.Integer,
        db.ForeignKey("class_sessions.id"),
        nullable=False,
        index=True
    )

    # Which student was marked
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Attendance result for this session
    # Expected backend values:
    # - present
    # - late
    # - absent
    status = db.Column(
        db.String(20),
        nullable=False,
        index=True
    )

    # Optional notes per student attendance record
    # Example:
    # "Late but accepted"
    # "Medical excuse pending"
    # "Manual correction"
    notes = db.Column(db.String(255), nullable=True)

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

    def __repr__(self):
        """
        Helpful for debugging and terminal testing.
        """
        return (
            f"<Attendance Session:{self.session_id} "
            f"Student:{self.student_id} "
            f"Status:{self.status}>"
        )