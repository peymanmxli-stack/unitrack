import sys
import os

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.models.attendance_model import Attendance

app = create_app()

with app.app_context():

    print("TOTAL ATTENDANCE ROWS =", Attendance.query.count())
    print("")

    rows = Attendance.query.all()

    for r in rows:
        print(
            "ID:", r.id,
            "| USER:", r.user_id,
            "| TYPE:", r.movement_type,
            "| DATE:", r.attendance_date,
            "| TIME:", r.movement_time
        )
