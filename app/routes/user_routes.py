"""
user_routes.py

API routes for user data.

Purpose:
- provide list of students for docente UI
"""

from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from app.models.user_model import User
from app.database import db

user_bp = Blueprint(
    "user",
    __name__,
    url_prefix="/api/users"
)


@user_bp.route("/students", methods=["GET"])
@login_required
def get_all_students():
    """
    Return all users with role 'estudiante'
    """

    # only docente or administrativo
    if current_user.role not in ["docente", "administrativo"]:
        return jsonify({
            "success": False,
            "error": "Unauthorized"
        }), 403

    users = db.session.query(User).filter_by(role="estudiante").all()

    return jsonify({
        "success": True,
        "total": len(users),
        "students": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "name": f"{u.first_name} {u.last_name}"
            }
            for u in users
        ]
    })