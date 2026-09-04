from functools import wraps
from flask import request, jsonify

ALLOWED_ROLES = {"Marketing", "Product", "Admin"}

def require_role(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            role = request.headers.get("X-User-Role")

            if not role:
                return jsonify({"error": "authentication required"}), 401

            if role not in roles:
                return jsonify({"error": "forbidden"}), 403

            return func(*args, **kwargs)
        return wrapper
    return decorator