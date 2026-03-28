"""
security.py

This file handles password hashing and verification.

Teaching idea:
We NEVER store real passwords in database.

Instead we store hashed versions.

This protects users even if database is stolen.

So when a user registers:
we hash the password.

When a user logs in:
we verify the password.
"""

from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password: str) -> str:
    """
    Convert plain password into hashed version.

    Example:
    "mypassword123" -> "pbkdf2:sha256:..."
    """
    return generate_password_hash(password)


def verify_password(hash_value: str, password: str) -> bool:
    """
    Check if entered password matches stored hash.

    Returns True if password is correct.
    """
    return check_password_hash(hash_value, password)