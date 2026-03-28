"""
app/__init__.py

This file creates and configures the Flask application.
"""

from flask import Flask
from flask_login import LoginManager

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

# User loader helper
from .services.user_service import get_user_by_id

# Flask-Login manager
login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{Config.DATABASE_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["SECRET_KEY"] = Config.SECRET_KEY

    db.init_app(app)

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
        from .models.user_model import User
        from .models.validation_code_model import ValidationCode
        from .models.class_group_model import ClassGroup
        from .models.class_enrollment_model import ClassEnrollment
        from .models.class_session_model import ClassSession
        from .models.attendance_model import Attendance
        from .models.access_log_model import AccessLog

        db.create_all()

        seed_default_admin()

    @app.route("/")
    def home():
        return "UniTrack backend is running successfully!"

    return app