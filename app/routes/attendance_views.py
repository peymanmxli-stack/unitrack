"""
attendance_views.py

Frontend view routes for docente attendance pages.

Teaching idea:
This file is responsible for rendering HTML pages for teachers.

At this stage, this file is designed to be SAFE:
- it creates the docente page routes
- it renders the templates without crashing
- it passes defensive default data
- it gives us a clean base to connect real backend data next

Why we do it this way:
Because the file was empty, the first professional step is to create
the view layer structure first, then in the next step we connect the
real services/models one by one.

Current pages supported:
- docente dashboard
- docente session history
- docente roster page

Next phase after this file:
connect real class/session/summary data from backend services.
"""

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from app.utils.role_required import role_required


attendance_views_bp = Blueprint("attendance_views", __name__, url_prefix="/docente")


@attendance_views_bp.route("/attendance")
@login_required
@role_required("docente")
def docente_dashboard_page():
    """
    Main docente dashboard page.

    Right now we pass an empty dashboard_items list safely.
    That means the template can render immediately without crashing.

    Next step:
    replace this placeholder with real dashboard data from:
    - teacher class groups
    - open session per class
    - last session per class
    - attendance summary per class
    """
    dashboard_items = []

    return render_template(
        "docente/docente_dashboard.html",
        page_title="Docente Dashboard",
        dashboard_items=dashboard_items,
        teacher_name=f"{current_user.first_name} {current_user.last_name}"
    )


@attendance_views_bp.route("/sessions/history")
@login_required
@role_required("docente")
def docente_session_history_page():
    """
    Session history page for teachers.

    We already support query reading from the URL:
    - search
    - status
    - date
    - page

    For now we render an empty history safely.
    Later we will replace this with real filtered backend data.
    """
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    date = request.args.get("date", "").strip()

    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1

    history_items = []

    pagination = {
        "page": page,
        "total_pages": 1,
        "total_items": 0,
        "start_index": 0,
        "end_index": 0,
        "has_prev": False,
        "has_next": False,
        "prev_page": None,
        "next_page": None,
    }

    return render_template(
        "docente/docente_session_history.html",
        page_title="Session History",
        history_items=history_items,
        pagination=pagination,
        active_filters={
            "search": search,
            "status": status,
            "date": date,
        }
    )


@attendance_views_bp.route("/attendance/session/<int:session_id>/roster")
@login_required
@role_required("docente")
def docente_roster_page(session_id):
    """
    Roster page for one teacher session.

    Right now this is also defensive:
    - session is represented with a simple placeholder object shape
    - summary has zero values
    - roster is empty

    This allows the template/UI to exist first.
    In the next step we will connect the real session query and
    real enrolled student roster data.
    """

    class SimpleObject:
        """
        Small helper object.

        Teaching idea:
        Jinja templates often use dot access like:
        session.id
        summary.total_students

        This helper lets us create simple placeholder objects
        with dot-style access until real database objects are connected.
        """
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    session = SimpleObject(
        id=session_id,
        is_open=False,
        start_time=None,
        end_time=None,
    )

    class_group = SimpleObject(
        id=0,
        display_name="Sample Class",
        subject_name="Pending Backend Connection",
        group_code="N/A",
        is_active=True,
    )

    summary = SimpleObject(
        total_students=0,
        present_count=0,
        absent_count=0,
        not_marked_count=0,
    )

    roster = []

    return render_template(
        "docente/docente_roster.html",
        page_title="Class Roster Attendance",
        session=session,
        class_group=class_group,
        summary=summary,
        roster=roster,
    )