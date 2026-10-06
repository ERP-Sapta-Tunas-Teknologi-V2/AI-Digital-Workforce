import os
os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["TORCH_COMPILE_DISABLE"] = "1"

from pathlib import Path
from ingestion.indexer import index_document, SUPPORTED_EXTENSIONS, ALLOWED_CATEGORIES
from ingestion.vectorstore import get_document_ids, delete_document
from utils.doc_screening import screen_document, extract_text_sample
from utils.minio_client import list_files, download_file
from utils.status_tracker import get_all_statuses, delete_status

SOURCE_DIR = Path("documents")

def sync_documents(category=None):
    categories = [category] if category else sorted(ALLOWED_CATEGORIES)

    for category in categories:
        sync_category(category)

def sync_category(category):
    superseded = {s["document_id"] for s in get_all_statuses()
                  if s.get("version_status") == "superseded"}  # perlu tambah kolom di select
    source_files = {}
    for f in list_files(category):
        if f["filename"].startswith("_archive/"):
            continue
        if Path(f["filename"]).suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        document_id = f"{category}:{Path(f['filename']).stem}"
        if document_id in superseded:
            continue
        source_files[document_id] = f["filename"]

    source_ids = set(source_files)
    db_ids = get_document_ids(category)
    new_ids, existing_ids, deleted_ids = source_ids - db_ids, source_ids & db_ids, db_ids - source_ids
    print(f"[SYNC] {category} | New: {len(new_ids)} | Existing: {len(existing_ids)} | Deleted: {len(deleted_ids)}")

    for document_id in new_ids | existing_ids:
        filename = source_files[document_id]
        file_bytes = download_file(category, filename).getvalue()
        should_block, flags = screen_document(
            document_id, file_bytes, text_sample=extract_text_sample(filename, file_bytes))
        if should_block:
            print(f"[SYNC] SKIPPED (flagged): {document_id} | flags={flags}")
            continue
        index_document(category, filename)

    for document_id in deleted_ids:
        delete_document(document_id)
        delete_status(document_id)