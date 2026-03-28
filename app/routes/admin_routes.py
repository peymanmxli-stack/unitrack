"""
admin_routes.py

Administrative routes for UniTrack.

Upgraded with:
- validation code generation (Head Admin action)
"""

from flask import Blueprint, jsonify, redirect, url_for, request
from flask_login import login_required, current_user

from datetime import datetime, timedelta
import secrets
import string

from app.database import db
from app.models.user_model import User
from app.models.attendance_model import Attendance
from app.models.validation_code_model import ValidationCode
from app.services.user_service import deactivate_user, activate_user
from app.utils.role_required import role_required


admin_bp = Blueprint("admin", __name__, url_prefix="/admin/api")


def admin_inactive_response():
    return jsonify({
        "success": False,
        "error": "User account is inactive"
    }), 403


def generate_random_code(length=8):
    """
    Generate secure university validation code.
    Example: A8K3J9XQ
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# =========================
# ⭐ CREATE VALIDATION CODE
# =========================
@admin_bp.route("/validation-codes/create", methods=["POST"])
@login_required
@role_required("administrativo")
def generate_validation_code():

    if not current_user.is_active_user:
        return redirect(url_for("admin_views.validation_codes_page"))

    expires_in_hours = request.form.get("expires_in_hours", type=int)
    purpose_note = request.form.get("purpose_note")

    if not expires_in_hours:
        expires_in_hours = 24

    code_value = generate_random_code()

    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

    new_code = ValidationCode(
        code=code_value,
        generated_by=current_user.id,
        expires_at=expires_at
    )

    db.session.add(new_code)
    db.session.commit()

    return redirect(url_for("admin_views.validation_codes_page"))


# =========================
# USERS ACTIVATE / DEACTIVATE
# =========================
@admin_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@login_required
@role_required("administrativo")
def admin_deactivate_user(user_id):

    if not current_user.is_active_user:
        return redirect(url_for("admin_views.users_page"))

    if current_user.id == user_id:
        return redirect(url_for("admin_views.users_page"))

    user = db.session.get(User, user_id)

    if not user:
        return redirect(url_for("admin_views.users_page"))

    deactivate_user(user.id)

    return redirect(url_for("admin_views.users_page"))


@admin_bp.route("/users/<int:user_id>/activate", methods=["POST"])
@login_required
@role_required("administrativo")
def admin_activate_user(user_id):

    if not current_user.is_active_user:
        return redirect(url_for("admin_views.users_page"))

    user = db.session.get(User, user_id)

    if not user:
        return redirect(url_for("admin_views.users_page"))

    activate_user(user.id)

    return redirect(url_for("admin_views.users_page"))