"""
database.py

This file creates the database connection for UniTrack.

Teaching idea:
Instead of creating the database object in random places,
we create it once here and then import it anywhere we need it.

This is the central database layer of the project.

Later:
- models will use this db object
- the app factory will connect this db object to Flask
- tables like users, attendance, and validation codes will be built from here
"""

from flask_sqlalchemy import SQLAlchemy

# Create the SQLAlchemy object.
# Right now it is not connected to the app yet.
# That connection will happen inside app/__init__.py
db = SQLAlchemy()