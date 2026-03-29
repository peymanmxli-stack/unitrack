"""
app/__init__.py

This file creates and configures the Flask application.
"""

from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy import inspect
import os

from config import Config
from .database import db

# Blueprints
from .routes.auth_routes import auth_bp
from .routes.attendance_routes import attendance_bp
from .routes.admin_routes import admin_bp
from .routes.admin_views import admin_views_bp
from .routes.enrollment_routes import enrollment_bp
from .routes.docente_views import docente_views_bp
from .routes.student_views import student_views_bp

# 🔥 FIX: import personal views
from .routes.personal_views import personal_views_bp

# Seeder
from .services.admin_seed_service import seed_default_admin

# 🔥 NEW: validation code service
from .services.validation_code_service import create_validation_code

# User loader helper
from .services.user_service import get_user_by_id

# Flask-Login manager
login_manager = LoginManager()
migrate = Migrate()


@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    app.config["SQLALCHEMY_DATABASE_URI"] = Config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = Config.SQLALCHEMY_TRACK_MODIFICATIONS

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", Config.SECRET_KEY)

    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)

    login_manager.login_view = None

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_views_bp)
    app.register_blueprint(enrollment_bp)
    app.register_blueprint(docente_views_bp)
    app.register_blueprint(student_views_bp)

    # 🔥 FIX: register personal blueprint
    app.register_blueprint(personal_views_bp)

    with app.app_context():
        # 🔥 FIX: required for Render free tier when migrations CLI is not available
        db.create_all()

        from .models.user_model import User
        from .models.validation_code_model import ValidationCode
        from .models.class_group_model import ClassGroup
        from .models.class_enrollment_model import ClassEnrollment
        from .models.class_session_model import ClassSession
        from .models.attendance_model import Attendance
        from .models.access_log_model import AccessLog

        existing_tables = inspect(db.engine).get_table_names()

        if "users" in existing_tables:
            admin_user, created = seed_default_admin()

            # 🔥 NEW: auto-create validation code if none exist
            existing_codes = db.session.query(ValidationCode).count()

            if existing_codes == 0 and admin_user:
                code = create_validation_code(
                    generated_by_user_id=admin_user.id,
                    expires_in_hours=24 * 7
                )
                print("AUTO VALIDATION CODE:", code.code)

    @app.route("/")
    def home():
        return redirect(url_for("auth.login_page"))

    return app
