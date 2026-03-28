"""
run.py

This is the main startup file for the UniTrack project.

Teaching idea:
Think of this file as the front door of the backend.

When we run this file:
- Flask app is created
- configuration is loaded
- later routes will be connected
- later database will be connected

For now, this file only starts the server in a clean professional way.
"""

from app import create_app

# We call the function that builds and returns the Flask app.
# This is the professional factory pattern.
app = create_app()

# This block means:
# "only run the server if this file is executed directly"
# It is very common and very important in Python projects.
if __name__ == "__main__":
    app.run(debug=True)