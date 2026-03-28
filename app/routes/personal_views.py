"""
personal_views.py

CLONE of student system for personal users.
"""

from datetime import datetime
from io import BytesIO
import base64
import hashlib
import os

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.database import db
from app.models.user_model import User
from app.services.access_log_service import (
    build_personal_access_table_rows,
    create_check_in,
    create_check_out,
    get_open_access_log_for_personal,
    get_personal_access_quick_stats,
    get_personal_by_id,
    get_personal_current_access_status,
)
from app.services.attendance_service import (
    build_personal_attendance_history_rows,
    get_personal_attendance_class_options,
    get_personal_attendance_summary,
)
from app.utils.role_required import role_required


personal_views_bp = Blueprint(
    "personal_views",
    __name__,
    url_prefix="/personal"
)


ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg"}


def _clean_text(value):
    return str(value or "").strip()


def _personal_full_name(personal):
    return f"{personal.first_name} {personal.last_name}".strip()


def _configuration_form_data():
    return {
        "first_name": current_user.first_name or "",
        "last_name": current_user.last_name or "",
        "username": current_user.username or "",
        "email": current_user.email or "",
        "phone": getattr(current_user, "phone", "") or "",
        "language": getattr(current_user, "language", "en") or "en",
    }


def _redirect_configuration_error(message):
    return redirect(url_for("personal_views.configuration_page", error=message))


def _redirect_configuration_message(message):
    return redirect(url_for("personal_views.configuration_page", message=message))


def _redirect_access_error(message):
    return redirect(url_for("personal_views.access_control_page", error=message))


def _redirect_access_message(message):
    return redirect(url_for("personal_views.access_control_page", message=message))


def build_personal_access_qr_payload(personal):
    """
    Build the raw text payload encoded inside the QR image.
    """

    personal_name = _personal_full_name(personal)

    return (
        f"UNITRACK|ACCESS|"
        f"personal_id={personal.id}|"
        f"username={personal.username}|"
        f"name={personal_name}"
    )


def build_personal_access_qr_id_code(personal):
    """
    Build a short manual fallback code for the personal.
    """

    raw_text = f"{personal.id}|{personal.username}|{personal.first_name}|{personal.last_name}"
    digest = hashlib.sha1(raw_text.encode("utf-8")).hexdigest().upper()

    first_two_digits = str(personal.id).zfill(2)[-2:]

    letters_pool = "".join([char for char in digest if char.isalpha()])
    two_letters = letters_pool[:2] if len(letters_pool) >= 2 else "QR"

    last_two_digits = str((len(personal.username) * 7 + personal.id) % 100).zfill(2)

    return f"{first_two_digits}{two_letters}{last_two_digits}"


def find_personal_by_access_qr_id_code(qr_id_code):
    """
    Resolve a personal from the short manual QR ID code.
    """

    qr_id_code = str(qr_id_code or "").strip().upper()

    if not qr_id_code:
        return None

    personals = User.query.filter_by(role="personal").all()

    for personal in personals:
        if build_personal_access_qr_id_code(personal) == qr_id_code:
            return personal

    return None


def parse_personal_access_qr_payload(qr_text):
    """
    Parse a UniTrack personal access QR payload.
    """

    if not qr_text:
        return None

    qr_text = qr_text.strip()

    if not qr_text.startswith("UNITRACK|ACCESS|"):
        return None

    parts = qr_text.split("|")

    if len(parts) < 5:
        return None

    payload_data = {}

    for item in parts[2:]:
        if "=" not in item:
            continue

        key, value = item.split("=", 1)
        payload_data[key.strip()] = value.strip()

    personal_id_text = payload_data.get("personal_id", "").strip()
    username = payload_data.get("username", "").strip()
    name = payload_data.get("name", "").strip()

    if not personal_id_text.isdigit():
        return None

    return {
        "personal_id": int(personal_id_text),
        "username": username,
        "name": name,
    }


def generate_qr_image_data_uri(qr_text):
    """
    Generate a QR image in memory and return it as a data URI.
    """

    try:
        import qrcode
    except ImportError:
        return None

    try:
        qr = qrcode.QRCode(
            version=1,
            box_size=8,
            border=2
        )
        qr.add_data(qr_text)
        qr.make(fit=True)

        image = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        encoded_image = base64.b64encode(buffer.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded_image}"

    except Exception:
        return None


def process_access_scan_qr_text(qr_text):
    """
    Central scan processor used by:
    - API scanner endpoint
    - browser scanner page
    """

    qr_text = str(qr_text or "").strip()

    if not qr_text:
        return {
            "success": False,
            "message": "QR text is required."
        }, 400

    personal = None
    parsed_payload = parse_personal_access_qr_payload(qr_text)

    if parsed_payload:
        personal_id = parsed_payload["personal_id"]
        qr_username = parsed_payload["username"]

        personal = get_personal_by_id(personal_id)

        if not personal:
            return {
                "success": False,
                "message": "Personal not found."
            }, 404

        if personal.username != qr_username:
            return {
                "success": False,
                "message": "QR validation failed. Personal data mismatch."
            }, 400

    else:
        personal = find_personal_by_access_qr_id_code(qr_text)

        if not personal:
            return {
                "success": False,
                "message": "Invalid UniTrack QR payload or QR ID code."
            }, 400

    open_log = get_open_access_log_for_personal(personal.id)

    try:
        if open_log:
            updated_log = create_check_out(
                personal_id=personal.id,
                notes="QR scanner automatic check-out"
            )

            return {
                "success": True,
                "action": "check_out",
                "message": "Check-Out realizado correctamente.",
                "personal_id": personal.id,
                "personal_name": _personal_full_name(personal),
                "username": personal.username,
                "qr_id_code": build_personal_access_qr_id_code(personal),
                "status": updated_log.access_status,
                "check_in_time": (
                    updated_log.check_in_time.isoformat()
                    if updated_log.check_in_time else None
                ),
                "check_out_time": (
                    updated_log.check_out_time.isoformat()
                    if updated_log.check_out_time else None
                )
            }, 200

        new_log = create_check_in(
            personal_id=personal.id,
            access_method="qr",
            notes="QR scanner automatic check-in"
        )

        return {
            "success": True,
            "action": "check_in",
            "message": "Check-In realizado correctamente.",
            "personal_id": personal.id,
            "personal_name": _personal_full_name(personal),
            "username": personal.username,
            "qr_id_code": build_personal_access_qr_id_code(personal),
            "status": new_log.access_status,
            "check_in_time": (
                new_log.check_in_time.isoformat()
                if new_log.check_in_time else None
            ),
            "check_out_time": (
                new_log.check_out_time.isoformat()
                if new_log.check_out_time else None
            )
        }, 200

    except ValueError as exc:
        return {
            "success": False,
            "message": str(exc)
        }, 400

    except Exception:
        return {
            "success": False,
            "message": "Unexpected scanner error while processing the QR."
        }, 500


@personal_views_bp.route("/dashboard")
@login_required
@role_required("personal", "administrativo")
def dashboard_page():
    personal_name = _personal_full_name(current_user)

    return render_template(
        "personal_dashboard.html",
        personal_name=personal_name,
        active_page="dashboard"
    )


@personal_views_bp.route("/access-control", methods=["GET"])
@login_required
@role_required("personal", "administrativo")
def access_control_page():
    """
    Personal access control page.
    """

    personal_name = _personal_full_name(current_user)

    selected_date = request.args.get("date", "").strip()
    access_message = request.args.get("message", "").strip()
    access_error = request.args.get("error", "").strip()

    parsed_date = None

    if selected_date:
        try:
            parsed_date = datetime.strptime(selected_date, "%m/%d/%Y").date()
        except ValueError:
            parsed_date = None
            access_error = "Fecha inválida. Usa el formato MM/DD/YYYY."

    all_records = build_personal_access_table_rows(current_user)

    if parsed_date:
        filtered_records = [
            record for record in all_records
            if record.get("date") == selected_date
        ]
    else:
        filtered_records = all_records

    for index, record in enumerate(filtered_records, start=1):
        record["row"] = index

    quick_stats = get_personal_access_quick_stats(current_user.id)
    current_access_status = get_personal_current_access_status(current_user.id)

    access_qr_payload = build_personal_access_qr_payload(current_user)
    access_qr_image = generate_qr_image_data_uri(access_qr_payload)
    access_qr_id_code = build_personal_access_qr_id_code(current_user)

    return render_template(
        "personal_access_control.html",
        personal_name=personal_name,
        active_page="access_control",
        demo_records=filtered_records,
        quick_stats=quick_stats,
        current_access_status=current_access_status,
        selected_date=selected_date,
        access_message=access_message,
        access_error=access_error,
        access_qr_payload=access_qr_payload,
        access_qr_image=access_qr_image,
        access_qr_id_code=access_qr_id_code
    )


@personal_views_bp.route("/attendance-history", methods=["GET"])
@login_required
@role_required("personal", "administrativo")
def attendance_history_page():
    """
    Real personal academic attendance history page.
    """

    personal_name = _personal_full_name(current_user)

    selected_date = request.args.get("date", "").strip()
    selected_class_name = request.args.get("class_name", "").strip()

    attendance_records = build_personal_attendance_history_rows(
        personal_id=current_user.id,
        selected_date=selected_date,
        selected_class_name=selected_class_name
    )

    class_options = get_personal_attendance_class_options(
        personal_id=current_user.id
    )

    summary = get_personal_attendance_summary(
        personal_id=current_user.id,
        selected_date=selected_date,
        selected_class_name=selected_class_name
    )

    return render_template(
        "personal_attendance_history.html",
        personal_name=personal_name,
        active_page="attendance_history",
        attendance_records=attendance_records,
        class_options=class_options,
        selected_date=selected_date,
        selected_class_name=selected_class_name,
        attendance_percentage=summary["attendance_percentage"],
        attendance_percentage_color=summary["attendance_percentage_color"],
        present_count=summary["present_count"],
        late_count=summary["late_count"],
        absent_count=summary["absent_count"]
    )


@personal_views_bp.route("/configuration", methods=["GET"])
@login_required
@role_required("personal", "administrativo")
def configuration_page():
    personal_name = _personal_full_name(current_user)

    profile_message = request.args.get("message", "").strip()
    profile_error = request.args.get("error", "").strip()

    return render_template(
        "personal_configuration.html",
        personal_name=personal_name,
        active_page="configuration",
        profile_message=profile_message,
        profile_error=profile_error,
        form_data=_configuration_form_data(),
        last_password_change=None
    )


@personal_views_bp.route("/configuration/update", methods=["POST"])
@login_required
@role_required("personal", "administrativo")
def configuration_update():
    first_name = _clean_text(request.form.get("first_name"))
    last_name = _clean_text(request.form.get("last_name"))
    email = _clean_text(request.form.get("email")).lower()
    phone = _clean_text(request.form.get("phone"))
    language = _clean_text(request.form.get("language"))

    if language not in ["en", "es"]:
        language = "en"

    if not first_name:
        return _redirect_configuration_error("El nombre es obligatorio.")

    if not last_name:
        return _redirect_configuration_error("El apellido es obligatorio.")

    if not email:
        return _redirect_configuration_error("El correo electrónico es obligatorio.")

    if not phone:
        return _redirect_configuration_error("El teléfono es obligatorio.")

    existing_email_user = User.query.filter(
        User.email == email,
        User.id != current_user.id
    ).first()

    if existing_email_user:
        return _redirect_configuration_error(
            "Ese correo electrónico ya está en uso por otro usuario."
        )

    try:
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.email = email
        current_user.phone = phone
        current_user.language = language

        db.session.commit()

        return _redirect_configuration_message(
            "Configuración actualizada correctamente."
        )

    except Exception:
        db.session.rollback()
        return _redirect_configuration_error(
            "No se pudo actualizar la configuración del personal."
        )


@personal_views_bp.route("/configuration/photo", methods=["POST"])
@login_required
@role_required("personal", "administrativo")
def configuration_update_photo():
    file = request.files.get("photo")

    if not file:
        return _redirect_configuration_error("No se seleccionó ninguna foto.")

    safe_filename = secure_filename(file.filename or "")

    if not safe_filename:
        return _redirect_configuration_error("Archivo inválido.")

    if "." not in safe_filename:
        return _redirect_configuration_error("Archivo inválido.")

    extension = safe_filename.rsplit(".", 1)[1].lower()

    if extension not in ALLOWED_PHOTO_EXTENSIONS:
        return _redirect_configuration_error("Formato no permitido.")

    upload_folder = os.path.join(
        current_app.root_path,
        "static",
        "uploads",
        "personals"
    )
    os.makedirs(upload_folder, exist_ok=True)

    final_filename = f"personal_{current_user.id}.{extension}"
    final_path = os.path.join(upload_folder, final_filename)

    try:
        file.save(final_path)

        current_user.photo_path = f"uploads/personals/{final_filename}"
        db.session.commit()

        return _redirect_configuration_message("Foto actualizada correctamente.")

    except Exception:
        db.session.rollback()
        return _redirect_configuration_error("No se pudo subir la foto.")


@personal_views_bp.route("/access-control/check-in", methods=["POST"])
@login_required
@role_required("personal", "administrativo")
def access_control_check_in():
    """
    Create a new university access check-in for the logged-in personal.
    """

    try:
        create_check_in(
            personal_id=current_user.id,
            access_method="qr",
            notes="Personal check-in from access control panel"
        )
        return _redirect_access_message("Check-In realizado correctamente.")

    except ValueError as exc:
        return _redirect_access_error(str(exc))

    except Exception:
        return _redirect_access_error("No se pudo registrar el Check-In.")


@personal_views_bp.route("/access-control/check-out", methods=["POST"])
@login_required
@role_required("personal", "administrativo")
def access_control_check_out():
    """
    Close the active university access log for the logged-in personal.
    """

    try:
        create_check_out(
            personal_id=current_user.id,
            notes="Personal check-out from access control panel"
        )
        return _redirect_access_message("Check-Out realizado correctamente.")

    except ValueError as exc:
        return _redirect_access_error(str(exc))

    except Exception:
        return _redirect_access_error("No se pudo registrar el Check-Out.")


@personal_views_bp.route("/access-control/scan", methods=["POST"])
@login_required
@role_required("personal", "administrativo")
def access_control_scan():
    """
    Protected scanner endpoint for QR-based campus access.
    """

    data = request.get_json(silent=True) or {}
    qr_text = str(data.get("qr_text", "")).strip()

    response_data, status_code = process_access_scan_qr_text(qr_text)
    return jsonify(response_data), status_code


@personal_views_bp.route("/access-control/scanner", methods=["GET", "POST"])
@login_required
@role_required("personal", "administrativo")
def access_control_scanner_page():
    """
    Simple browser-based QR scanner simulation page.
    """

    personal_name = _personal_full_name(current_user)
    scan_result = None
    qr_text_value = ""

    if request.method == "POST":
        qr_text_value = request.form.get("qr_text", "").strip()
        response_data, status_code = process_access_scan_qr_text(qr_text_value)

        scan_result = {
            "success": response_data.get("success", False),
            "message": response_data.get("message", ""),
            "action": response_data.get("action", ""),
            "personal_name": response_data.get("personal_name", ""),
            "username": response_data.get("username", ""),
            "qr_id_code": response_data.get("qr_id_code", ""),
            "status": response_data.get("status", ""),
            "check_in_time": response_data.get("check_in_time", ""),
            "check_out_time": response_data.get("check_out_time", ""),
            "status_code": status_code
        }

    return render_template(
        "personal_qr_scanner.html",
        personal_name=personal_name,
        active_page="access_control",
        scan_result=scan_result,
        qr_text_value=qr_text_value
    )