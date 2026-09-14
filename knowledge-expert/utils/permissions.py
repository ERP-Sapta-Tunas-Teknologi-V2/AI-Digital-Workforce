from functools import wraps
from flask import request, jsonify

ALLOWED_ROLES = {"Marketing", "Product", "Admin"}

CATEGORY_ACCESS = {
    "sop": None,  # None = semua role
    "datasheet": {"Sales", "Solution Architect"},
    "pricelist": {"Sales"},
    "guide": {"Solution Architect"},
    "meeting": {"Sales"},
    "training": None,
}

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

def get_allowed_categories(role):
    """Return None jika tidak ada filter (role tidak dikirim), atau list kategori yang diizinkan."""

    if role is None:
        return None  # no filter — dipakai widget publik tanpa header

    return [
        cat for cat, allowed in CATEGORY_ACCESS.items()
        if allowed is None or role in allowed
    ]