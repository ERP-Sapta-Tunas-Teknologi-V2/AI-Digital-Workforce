import uuid
from pathlib import Path
from threading import Thread
from flask import Blueprint, request, jsonify

from utils.permissions import require_role
from ingestion.indexer import index_document
from sync.sync import sync_documents

admin_bp = Blueprint("admin", __name__)

ALLOWED_EXTENSIONS = {".docx"}
ALLOWED_CATEGORIES = {"berita", "stt"}

def sync_background(category):
    try:
        sync_documents(category)
    except Exception as e:
        print(f"[SYNC] failed: {e}")

def ingest_background(file_path):
    try:
        index_document(file_path)
    except Exception as e:
        print(f"[INGEST] failed: {e}")

@admin_bp.route("/sync", methods=["POST"])
@require_role("Admin")
def sync():
    data = request.get_json(silent=True) or {}
    category = data.get("category")

    if category not in ALLOWED_CATEGORIES:
        return jsonify({"error": f"category must be one of {sorted(ALLOWED_CATEGORIES)}"}), 400

    Thread(target=sync_background, args=(category,), daemon=True).start()
    return jsonify({"message": f"sync started for category '{category}'"}), 202

@admin_bp.route("/ingest", methods=["POST"])
@require_role("Admin")
def ingest():
    data = request.get_json(silent=True) or {}
    file_path = data.get("path")

    if not file_path or not isinstance(file_path, str):
        return jsonify({"error": "path is required"}), 400

    path = Path(file_path)

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"unsupported file type: {path.suffix}"}), 400

    if not path.is_file():
        return jsonify({"error": "file not found"}), 404

    Thread(target=ingest_background, args=(str(path),), daemon=True).start()
    return jsonify({"message": "ingest started", "file": path.name}), 202