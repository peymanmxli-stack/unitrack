"""
admin_views.py

Frontend view routes for the UniTrack admin panel.

ADMIN RESPONSIBILITIES:
- system dashboard
- user monitoring
- validation code lifecycle monitoring
- role analytics
- academic class group monitoring
"""

from flask import Blueprint, render_template, request
from flask_login import login_required

from datetime import datetime

from app.models.user_model import User
from app.models.validation_code_model import ValidationCode
from app.models.class_group_model import ClassGroup
from app.utils.role_required import role_required


admin_views_bp = Blueprint("admin_views", __name__, url_prefix="/admin")


# ==========================================
# DASHBOARD (SYSTEM ANALYTICS ONLY)
# ==========================================
@admin_views_bp.route("/dashboard")
@login_required
@role_required("administrativo")
def dashboard_page():

    total_users = User.query.count()
    active_users = User.query.filter_by(is_active_user=True).count()
    inactive_users = User.query.filter_by(is_active_user=False).count()

    total_validation_codes = ValidationCode.query.count()
    used_validation_codes = ValidationCode.query.filter_by(is_used=True).count()

    expired_validation_codes = 0
    usable_validation_codes = 0

    codes = ValidationCode.query.all()

    for code in codes:
        if code.is_expired():
            expired_validation_codes += 1
        if code.can_be_used():
            usable_validation_codes += 1

    # ⭐ ROLE DISTRIBUTION
    role_counts_map = {}

    users = User.query.all()

    for user in users:
        role = user.role or "unknown"
        role_counts_map[role] = role_counts_map.get(role, 0) + 1

    role_labels = list(role_counts_map.keys())
    role_counts = list(role_counts_map.values())

    analytics = {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "total_validation_codes": total_validation_codes,
        "used_validation_codes": used_validation_codes,
        "expired_validation_codes": expired_validation_codes,
        "usable_validation_codes": usable_validation_codes,
        "role_labels": role_labels,
        "role_counts": role_counts
    }

    return render_template(
        "admin_dashboard.html",
        analytics=analytics
    )


# ==========================================
# USERS PAGE
# ==========================================
@admin_views_bp.route("/users")
@login_required
@role_required("administrativo")
def users_page():

    search = request.args.get("search")
    role = request.args.get("role")
    status = request.args.get("status")
    sort = request.args.get("sort", "id_asc")

    query = User.query

    if search:
        query = query.filter(
            User.username.ilike(f"%{search}%")
        )

    if role:
        query = query.filter(User.role == role)

    if status == "active":
        query = query.filter(User.is_active_user == True)

    if status == "inactive":
        query = query.filter(User.is_active_user == False)

    if sort == "id_desc":
        query = query.order_by(User.id.desc())
    else:
        query = query.order_by(User.id.asc())

    users = query.all()

    return render_template(
        "admin_users.html",
        users=users
    )


# ==========================================
# VALIDATION CODES PAGE
# ==========================================
@admin_views_bp.route("/validation-codes")
@login_required
@role_required("administrativo")
def validation_codes_page():

    search = request.args.get("search")
    status = request.args.get("status")

    query = ValidationCode.query

    if search:
        query = query.filter(
            ValidationCode.code.ilike(f"%{search}%")
        )

    codes = query.order_by(
        ValidationCode.created_at.desc()
    ).all()

    now = datetime.utcnow()

    filtered_codes = []

    for code in codes:

        if code.expires_at and not code.is_used:
            remaining = code.expires_at - now

            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                code.remaining_time_text = f"{hours}h {minutes}m"
            else:
                code.remaining_time_text = "Expired"
        else:
            code.remaining_time_text = None

        if status == "usable" and not code.can_be_used():
            continue

        if status == "used" and not code.is_used:
            continue

        if status == "expired" and not code.is_expired():
            continue

        filtered_codes.append(code)

    return render_template(
        "admin_validation_codes.html",
        validation_codes=filtered_codes
    )


# ==========================================
# CLASS GROUPS PAGE
# ==========================================
@admin_views_bp.route("/class-groups")
@login_required
@role_required("administrativo")
def class_groups_page():
    """
    Admin academic class group page.

    Teaching idea:
    This page lets admin see the academic structure that powers docente attendance.

    Why this matters:
    If no class groups exist for a teacher, the teacher dashboard will look empty.
    So admin needs a place to create and monitor those class groups.
    """

    search = request.args.get("search")
    status = request.args.get("status")

    query = ClassGroup.query

    if search:
        query = query.filter(
            ClassGroup.subject_name.ilike(f"%{search}%") |
            ClassGroup.group_code.ilike(f"%{search}%")
        )

    if status == "active":
        query = query.filter(ClassGroup.is_active == True)

    if status == "inactive":
        query = query.filter(ClassGroup.is_active == False)

    class_groups = query.order_by(
        ClassGroup.subject_name.asc(),
        ClassGroup.group_code.asc()
    ).all()

    docentes = User.query.filter_by(role="docente").order_by(User.first_name.asc()).all()

    return render_template(
        "admin_class_groups.html",
        class_groups=class_groups,
        docentes=docentes
    )