"""
class_enrollment_model.py

Professional enrollment model for UniTrack.

Teaching idea:
A real university system does NOT store student IDs
directly inside ClassGroup.

Why?

Because:

- One student can belong to MANY classes
- One class contains MANY students
- Enrollment itself may need metadata

Example metadata:
- enrollment date
- enrollment status
- notes
- academic period later
"""

from datetime import datetime

from app.database import db


class ClassEnrollment(db.Model):
    """
    Enrollment = connection between student and class group.

    This model answers:
    - which student belongs to which class
    - when they joined
    - whether they are still active in that class
    """

    __tablename__ = "class_enrollments"

    id = db.Column(db.Integer, primary_key=True)

    class_group_id = db.Column(
        db.Integer,
        db.ForeignKey("class_groups.id"),
        nullable=False,
        index=True
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # If a student drops the class later
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    joined_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    notes = db.Column(db.Text, nullable=True)

    # Relationship:
    # enrollment -> student user
    #
    # Important:
    # this now matches the User model:
    # student_class_enrollments <-> student
    student = db.relationship(
        "User",
        foreign_keys=[student_id],
        back_populates="student_class_enrollments",
        lazy=True
    )

    def __repr__(self):
        return f"<Enrollment class={self.class_group_id} student={self.student_id}>"