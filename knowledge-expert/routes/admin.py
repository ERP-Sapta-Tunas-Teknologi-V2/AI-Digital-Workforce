from pathlib import Path
from threading import Thread
from flask import Blueprint, request, jsonify, send_file

from utils.permissions import require_role
from utils.locks import try_acquire, release
from utils.minio_client import file_exists, upload_file, list_files, delete_file, download_file, archive_file
from utils.status_tracker import get_all_statuses, delete_status, get_active_version, supersede_status, reset_stale_processing
from utils.doc_screening import screen_document, find_duplicate, extract_text_sample
from utils.supabase_admin import supabase
from ingestion.indexer import index_document
from ingestion.vectorstore import delete_document as delete_vectors
from sync.sync import sync_documents, SUPPORTED_EXTENSIONS, ALLOWED_CATEGORIES

admin_bp = Blueprint("admin", __name__)

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
}

VERSIONED_CATEGORIES = {"pricelist"}  # kritikal, bisa diperluas nanti

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
@require_role("Admin")
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
@require_role("Admin")
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

    document_id = f"{category}:{Path(filename).stem}"
    flag_check = supabase.table("document_flags").select("flag_type").eq("document_id", document_id).execute()
    blocking = [f["flag_type"] for f in (flag_check.data or []) if f["flag_type"] in {"duplicate", "confidential"}]

    if blocking:
        return jsonify({
            "error": f"document flagged as {blocking}, ingest blocked pending review",
            "hint": "gunakan endpoint override jika ingin memaksa ingest"
        }), 409

    lock_key = f"ingest:{category}/{filename}"
    if not try_acquire(lock_key):
        return jsonify({"error": f"ingest already running for '{filename}'"}), 409

    Thread(target=ingest_background, args=(category, filename), daemon=True).start()

    return jsonify({"message": "ingest started", "file": filename}), 202

@admin_bp.route("/documents/upload", methods=["POST"])
@require_role("Admin")
def upload():
    file = request.files.get("file")
    category = request.form.get("category")
    force_replace = request.form.get("replace", "false").lower() == "true"
    supersedes = request.form.get("supersedes")  # opsional: filename lama yang digantikan (nama file baru berbeda)

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

    document_id = f"{category}:{Path(filename).stem}"
    new_document_id = document_id

    # --- Deteksi versi lama yang perlu di-supersede ---
    old_document_id = None

    if category in VERSIONED_CATEGORIES:
        if supersedes:
            # Skenario B: nama file berbeda, admin eksplisit menyebutkan file lama
            old_document_id = f"{category}:{Path(supersedes).stem}"
        elif force_replace and file_exists(category, filename):
            # Skenario A: nama file sama, replace file yang sudah ada
            old_document_id = new_document_id
        else:
            # Skenario C: nama file baru, tapi ada versi aktif lain di kategori yang sama
            active_versions = [
                v for v in get_active_version(category)
                if v["document_id"] != new_document_id
            ]
            if len(active_versions) == 1:
                old_document_id = active_versions[0]["document_id"]
            elif len(active_versions) > 1:
                return jsonify({
                    "error": "multiple active versions found, specify 'supersedes' explicitly",
                    "active_versions": [v["document_id"] for v in active_versions]
                }), 409

    text_sample = extract_text_sample(filename, file_bytes)
    should_block, flags = screen_document(document_id, file_bytes, text_sample=text_sample)

    # --- Skenario A: nama file sama -> arsipkan file lama & pindahkan row status-nya ---
    if old_document_id == new_document_id and file_exists(category, filename):
        archived_key = archive_file(category, filename)
        archived_filename = Path(archived_key).name  # mis. "20260911151203_cisco.xlsx"

        archived_document_id = f"{category}:_archive_{Path(archived_filename).stem}"

        old_status = supabase.table("document_status").select("*").eq("document_id", old_document_id).execute()
        if old_status.data:
            old_row = old_status.data[0]
            supabase.table("document_status").insert({
                **{k: v for k, v in old_row.items() if k not in {"document_id"}},
                "document_id": archived_document_id,
                "source": archived_filename,
            }).execute()
            supersede_status(archived_document_id, new_document_id)
            delete_status(old_document_id)  # hapus row asli supaya tidak konflik saat re-ingest

        old_document_id = None  # sudah ditangani, cegah masuk ke blok Skenario B/C di bawah

    upload_file(category=category, filename=filename, file_stream=file, length=len(file_bytes), content_type=mime_type)

    # --- Skenario B & C: nama file berbeda -> non-aktifkan vector & status versi lama ---
    superseded_id = None
    if old_document_id and old_document_id != new_document_id:
        delete_vectors(old_document_id)
        supersede_status(old_document_id, new_document_id)
        superseded_id = old_document_id

    if should_block:
        reasons = ", ".join(f"{flag_type}: {detail}" for flag_type, detail in flags)
        return jsonify({
            "warning": "document flagged for review",
            "flags": [{"type": t, "detail": d} for t, d in flags],
            "message": f'File di-upload tetapi review diperlukan sebelum di-ingest karena "{reasons}".'
        }), 200

    return jsonify({
        "message": "File uploaded successfully",
        "category": category,
        "filename": filename,
        "document_id": document_id,
        "superseded": superseded_id
    }), 201

@admin_bp.route("/documents", methods=["GET"])
@require_role("Admin")
def documents():
    reset_stale_processing()
    category = request.args.get("category")

    files = list_files(category)
    statuses = get_all_statuses()

    status_map = {s["document_id"]: s for s in statuses}

    flags_result = supabase.table("document_flags").select("document_id, flag_type, detail, duplicate_of").execute()
    flags_map = {}
    for row in flags_result.data or []:
        flags_map.setdefault(row["document_id"], []).append(row)

    for f in files:
        is_archived = f["path"].split("/", 1)[-1].startswith("_archive/") if "/" in f["path"] else False
        # deteksi path arsip: category/_archive/filename
        path_parts = f["path"].split("/")
        is_archived = len(path_parts) >= 2 and path_parts[1] == "_archive"

        if is_archived:
            stem = Path(f["filename"]).stem  # "20260911154249_belimo"
            document_id = f"{f['category']}:_archive_{stem}"
        else:
            document_id = f"{f['category']}:{Path(f['filename']).stem}"

        status_entry = status_map.get(document_id)

        f["document_id"] = document_id
        f["ingest_status"] = status_entry["status"] if status_entry else "not_ingested"
        f["last_ingested_at"] = status_entry["last_ingested_at"] if status_entry else None
        f["version_status"] = status_entry.get("version_status", "active") if status_entry else "active"
        f["superseded_by"] = status_entry.get("superseded_by") if status_entry else None
        f["uploaded_at_wib"] = _to_wib(f["uploaded_at"])
        f["last_ingested_at_wib"] = _to_wib(f["last_ingested_at"]) if status_entry else None
        f["is_archived"] = is_archived

        doc_flags = flags_map.get(document_id, [])
        f["flags"] = [
            {"type": fl["flag_type"], "detail": fl["detail"], "duplicate_of": fl.get("duplicate_of")}
            for fl in doc_flags
            if fl["flag_type"] != "clean"
        ]

    return jsonify(files)

@admin_bp.route("/un-ingest", methods=["POST"])
@require_role("Admin")
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
        delete_vectors(document_id)
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
@require_role("Admin")
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
        delete_vectors(document_id)

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
@require_role("Admin")
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