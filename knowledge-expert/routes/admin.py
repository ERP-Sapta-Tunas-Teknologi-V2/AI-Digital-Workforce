from pathlib import Path
from threading import Thread
from flask import Blueprint, request, jsonify, send_file

from utils.permissions import require_role
from utils.locks import try_acquire, release
from utils.minio_client import file_exists, upload_file, list_files, delete_file, download_file
from utils.status_tracker import get_all_statuses, delete_status
from ingestion.indexer import index_document
from ingestion.vectorstore import delete_document
from sync.sync import sync_documents, SUPPORTED_EXTENSIONS, ALLOWED_CATEGORIES

admin_bp = Blueprint("admin", __name__)

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
}

def sync_background(category):
    lock_key = f"sync:{category or 'all'}"

    try:
        sync_documents(category)
    except Exception as e:
        print(f"[SYNC] failed: {e}")
    finally:
        release(lock_key)

def ingest_background(category, filename):
    lock_key = f"ingest:{category}/{filename}"

    try:
        index_document(category, filename)
    except Exception as e:
        print(f"[INGEST] failed: {e}")
    finally:
        release(lock_key)

@admin_bp.route("/sync", methods=["POST"])
# @require_role("Admin")
def sync():
    data = request.get_json(silent=True) or {}
    category = data.get("category")

    if category is not None:
        if not isinstance(category, str) or category not in ALLOWED_CATEGORIES:
            return jsonify({"error": f"category must be one of {sorted(ALLOWED_CATEGORIES)}"}), 400

    lock_key = f"sync:{category or 'all'}"
    if not try_acquire(lock_key):
        return jsonify({"error": f"sync already running for '{category or 'all'}'"}), 409

    Thread(target=sync_background, args=(category,), daemon=True).start()

    message = f"sync started for category '{category}'" if category else "sync started for all categories"
    return jsonify({"message": message}), 202

@admin_bp.route("/ingest", methods=["POST"])
# @require_role("Admin")
def ingest():
    data = request.get_json(silent=True) or {}
    category = data.get("category")
    filename = data.get("filename")

    if not category or category not in ALLOWED_CATEGORIES:
        return jsonify({"error": f"category must be one of {sorted(ALLOWED_CATEGORIES)}"}), 400

    if not filename or not isinstance(filename, str):
        return jsonify({"error": "filename is required"}), 400

    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"unsupported file type: {ext}"}), 400

    if not file_exists(category, filename):
        return jsonify({"error": "file not found in storage"}), 404

    lock_key = f"ingest:{category}/{filename}"
    if not try_acquire(lock_key):
        return jsonify({"error": f"ingest already running for '{filename}'"}), 409

    Thread(target=ingest_background, args=(category, filename), daemon=True).start()

    return jsonify({"message": "ingest started", "file": filename}), 202

@admin_bp.route("/documents/upload", methods=["POST"])
# @require_role("Admin")
def upload():
    file = request.files.get("file")
    category = request.form.get("category")
    force_replace = request.form.get("replace", "false").lower() == "true"

    if not file or not file.filename:
        return jsonify({"error": "file is required"}), 400

    if not category or category not in ALLOWED_CATEGORIES:
        return jsonify({"error": f"category must be one of {sorted(ALLOWED_CATEGORIES)}"}), 400

    filename = file.filename
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"unsupported file type: {ext}"}), 400

    if file_exists(category, filename) and not force_replace:
        return jsonify({
            "exists": True,
            "message": f"File '{filename}' already exists in category '{category}'. Replace it?"
        }), 409

    file_bytes = file.read()
    file.seek(0)

    mime_type = MIME_TYPES.get(ext, file.content_type or "application/octet-stream")

    upload_file(
        category=category,
        filename=filename,
        file_stream=file,
        length=len(file_bytes),
        content_type=mime_type
    )

    return jsonify({
        "message": "File uploaded successfully",
        "category": category,
        "filename": filename
    }), 201

@admin_bp.route("/documents", methods=["GET"])
# @require_role("Admin")
def documents():
    category = request.args.get("category")

    files = list_files(category)
    statuses = get_all_statuses()

    status_map = {s["document_id"]: s for s in statuses}

    for f in files:
        document_id = f"{f['category']}:{f['filename'].rsplit('.', 1)[0]}"
        status_entry = status_map.get(document_id)

        f["document_id"] = document_id
        f["ingest_status"] = status_entry["status"] if status_entry else "not_ingested"
        f["last_ingested_at"] = status_entry["last_ingested_at"] if status_entry else None

        f["uploaded_at_wib"] = _to_wib(f["uploaded_at"])
        f["last_ingested_at_wib"] = _to_wib(f["last_ingested_at"]) if status_entry else None

    return jsonify(files)

@admin_bp.route("/un-ingest", methods=["POST"])
# @require_role("Admin")
def un_ingest():
    data = request.get_json(silent=True) or {}

    category = data.get("category")
    filename = data.get("filename")

    if not category or category not in ALLOWED_CATEGORIES:
        return jsonify({"error": "invalid category"}), 400

    if not filename or not isinstance(filename, str):
        return jsonify({"error": "filename is required"}), 400

    document_id = f"{category}:{Path(filename).stem}"

    try:
        delete_document(document_id)
        delete_status(document_id)

        return jsonify({
            "message": "Document un-ingested successfully",
            "document_id": document_id
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

@admin_bp.route("/documents/delete", methods=["DELETE"])
# @require_role("Admin")
def delete_document_endpoint():
    data = request.get_json(silent=True) or {}

    category = data.get("category")
    filename = data.get("filename")

    if not category or category not in ALLOWED_CATEGORIES:
        return jsonify({"error": "invalid category"}), 400

    if not filename or not isinstance(filename, str):
        return jsonify({"error": "filename is required"}), 400

    if not file_exists(category, filename):
        return jsonify({"error": "file not found in storage"}), 404

    document_id = f"{category}:{Path(filename).stem}"

    try:
        # Hapus vector database
        delete_document(document_id)

        # Hapus status ingest
        delete_status(document_id)

        # Hapus file MinIO
        delete_file(category, filename)

        return jsonify({
            "message": "Document deleted successfully",
            "category": category,
            "filename": filename
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

@admin_bp.route("/documents/download", methods=["GET"])
# @require_role("Admin")
def download_document():
    category = request.args.get("category")
    filename = request.args.get("filename")

    if not category or category not in ALLOWED_CATEGORIES:
        return jsonify({
            "error": f"category must be one of {sorted(ALLOWED_CATEGORIES)}"
        }), 400

    if not filename or not isinstance(filename, str):
        return jsonify({"error": "filename is required"}), 400

    if not file_exists(category, filename):
        return jsonify({"error": "file not found in storage"}), 404

    try:
        file_stream = download_file(category, filename)

        ext = Path(filename).suffix.lower()
        mimetype = MIME_TYPES.get(ext, "application/octet-stream")

        return send_file(
            file_stream,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        print(f"[DOWNLOAD] failed: {e}")
        return jsonify({
            "error": "failed to download document"
        }), 500

def _to_wib(iso_timestamp):
    if not iso_timestamp:
        return None

    from datetime import datetime, timezone, timedelta

    dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    wib = dt.astimezone(timezone(timedelta(hours=7)))
    return wib.strftime("%Y-%m-%d %H:%M:%S WIB")