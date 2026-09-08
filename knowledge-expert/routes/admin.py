from pathlib import Path
from threading import Thread
from flask import Blueprint, request, jsonify

from utils.permissions import require_role
from utils.locks import try_acquire, release, is_locked
from ingestion.indexer import index_document
from sync.sync import sync_documents, SUPPORTED_EXTENSIONS, ALLOWED_CATEGORIES

admin_bp = Blueprint("admin", __name__)

def sync_background(category):
    lock_key = f"sync:{category or 'all'}"

    if not try_acquire(lock_key):
        print(f"[SYNC] skipped: already running for '{category or 'all'}'")
        return

    try:
        sync_documents(category)
    except Exception as e:
        print(f"[SYNC] failed: {e}")
    finally:
        release(lock_key)

def ingest_background(file_path):
    lock_key = f"ingest:{file_path}"

    if not try_acquire(lock_key):
        print(f"[INGEST] skipped: already running for '{file_path}'")
        return

    try:
        index_document(file_path)
    except Exception as e:
        print(f"[INGEST] failed: {e}")
    finally:
        release(lock_key)

@admin_bp.route("/sync", methods=["POST"])
@require_role("Admin")
def sync():
    data = request.get_json(silent=True) or {}
    category = data.get("category")

    if category is not None:
        if not isinstance(category, str) or category not in ALLOWED_CATEGORIES:
            return jsonify({"error": f"category must be one of {sorted(ALLOWED_CATEGORIES)}"}), 400

    lock_key = f"sync:{category or 'all'}"
    if is_locked(lock_key):
        return jsonify({"error": f"sync already running for '{category or 'all'}'"}), 409

    Thread(target=sync_background, args=(category,), daemon=True).start()

    message = f"sync started for category '{category}'" if category else "sync started for all categories"
    return jsonify({"message": message}), 202

@admin_bp.route("/ingest", methods=["POST"])
@require_role("Admin")
def ingest():
    data = request.get_json(silent=True) or {}
    file_path = data.get("path")

    if not file_path or not isinstance(file_path, str):
        return jsonify({"error": "path is required"}), 400

    path = Path(file_path)

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"unsupported file type: {path.suffix}"}), 400

    if not path.is_file():
        return jsonify({"error": "file not found"}), 404

    if is_locked(f"ingest:{str(path)}"):
        return jsonify({"error": f"ingest already running for '{path.name}'"}), 409

    Thread(target=ingest_background, args=(str(path),), daemon=True).start()

    return jsonify({"message": "ingest started", "file": path.name}), 202