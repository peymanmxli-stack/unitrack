"""
role_required.py

This file provides role-based access protection for UniTrack.

Teaching idea:
Sometimes login alone is not enough.

Example:
- a student can log in
- but that does NOT mean the student should open admin pages

So we create a decorator that checks the current user's role
before allowing access to a route.

This will be used later like this:

@role_required("administrativo")
def admin_dashboard():
    ...
"""

from functools import wraps

from flask import jsonify, redirect, request, url_for
from flask_login import current_user


def wants_json_response():
    """
    Detect whether the current request expects JSON.

    Why this matters:
    - browser pages should redirect
    - API clients should receive JSON
    """

    if request.path.startswith("/api/"):
        return True

    accept_header = request.headers.get("Accept", "")
    if "application/json" in accept_header.lower():
        return True

    if request.is_json:
        return True

    return False


def role_required(*allowed_roles):
    """
    Allow access only if the logged-in user has one of the allowed roles.

    Example:
    @role_required("administrativo")
    @role_required("docente", "administrativo")
    """

    def decorator(view_function):
        @wraps(view_function)
        def wrapper(*args, **kwargs):

            # First make sure user is authenticated
            if not current_user.is_authenticated:
                if wants_json_response():
                    return jsonify({
                        "success": False,
                        "error": "Authentication required"
                    }), 401

                return redirect(url_for("auth.login_page"))

            # Optional safety check for disabled users
            if hasattr(current_user, "is_active_user") and not current_user.is_active_user:
                if wants_json_response():
                    return jsonify({
                        "success": False,
                        "error": "User account is inactive"
                    }), 403

                return redirect(url_for("auth.login_page"))

            # Role protection
            current_role = getattr(current_user, "role", None)

            if current_role not in allowed_roles:
                if wants_json_response():
                    return jsonify({
                        "success": False,
                        "error": "Access denied",
                        "required_roles": list(allowed_roles),
                        "your_role": current_role
                    }), 403

                # Browser-safe fallback:
                # send user to the correct dashboard for their own role
                if current_role == "administrativo":
                    return redirect("/admin/dashboard")
                if current_role == "docente":
                    return redirect("/docente/dashboard")
                if current_role == "personal":
                    return redirect("/personal/dashboard")
                if current_role == "estudiante":
                    return redirect("/student/dashboard")

                return redirect(url_for("auth.login_page"))

            return view_function(*args, **kwargs)

        return wrapper

    return decorator