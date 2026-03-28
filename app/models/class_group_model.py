"""
class_group_model.py

Professional academic class/group model for UniTrack.

Teaching idea:
Before a teacher can mark attendance, the system must first know:

- what class exists
- what the class is called
- what subject it belongs to
- which teacher owns the class
- which students belong to that class

Examples:
- Programming 1A
- Databases 3AFM
- Software Quality 3AFM

Important architecture update:
Attendance is no longer linked directly to ClassGroup.

Now the professional structure is:

ClassGroup
    -> enrolled students
    -> ClassSession
        -> Attendance

This is better because:
- teacher can open attendance from a real roster
- frontend can show the students of a class
- attendance marking becomes safer and easier
- the system becomes closer to a real university platform
"""

from datetime import datetime

from app.database import db


class ClassGroup(db.Model):
    """
    ClassGroup = one teacher-managed university class.

    This model helps the system answer:
    - Which teacher teaches this group?
    - What is the subject name?
    - What is the group code?
    - Is this class currently active?
    - Which students are enrolled in this class?
    """

    __tablename__ = "class_groups"

    id = db.Column(db.Integer, primary_key=True)

    # Example:
    # "Programming Fundamentals"
    # "Databases"
    subject_name = db.Column(db.String(150), nullable=False)

    # Example:
    # "1A"
    # "3AFM"
    # "TI-02"
    group_code = db.Column(db.String(50), nullable=False)

    # Optional human description
    description = db.Column(db.Text, nullable=True)

    # Which docente owns this class
    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # If later a class should be hidden/archived,
    # we do not need to delete it from the database.
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationship:
    # one class/group -> many sessions
    #
    # Teaching idea:
    # a class does not directly store attendance anymore.
    # first the teacher opens a session,
    # then attendance is marked inside that session.
    sessions = db.relationship(
        "ClassSession",
        backref="class_group",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # Relationship:
    # one class/group -> many student enrollments
    #
    # Important:
    # we use a separate enrollment table instead of storing
    # student IDs directly inside this model.
    #
    # Why?
    # Because in professional systems:
    # - one student can belong to many classes
    # - one class can contain many students
    # - enrollment may later need extra fields
    #   like status, joined_at, notes, etc.
    enrollments = db.relationship(
        "ClassEnrollment",
        backref="class_group",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def class_display_name(self):
        """
        Clean text for frontend tables and dropdowns.

        Example output:
        Databases - 3AFM
        """
        return f"{self.subject_name} - {self.group_code}"

    def __repr__(self):
        return f"<ClassGroup {self.subject_name} {self.group_code}>"