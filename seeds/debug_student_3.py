import sys
import os

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.models.user_model import User

app = create_app()

with app.app_context():
    student = User.query.get(3)

    if student:
        print("ID:", student.id)
        print("USERNAME:", student.username)
        print("NAME:", student.first_name, student.last_name)
        print("ROLE:", student.role)
    else:
        print("Student with ID 3 not found")