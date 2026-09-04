import os
os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["TORCH_COMPILE_DISABLE"] = "1"

from pathlib import Path
from ingestion.indexer import index_document
from rag.vectorstore import get_document_ids, delete_document

SOURCE_DIR = Path("stt")
SUPPORTED_EXTENSIONS = {".docx"}

def sync_documents():
    source_files = {}

    for path in SOURCE_DIR.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS: 
            continue

        document_id = f"{path.stem}"
        source_files[document_id] = path

    source_ids = set(source_files)
    db_ids = get_document_ids()

    new_ids = source_ids - db_ids
    existing_ids = source_ids & db_ids
    deleted_ids = db_ids - source_ids

    print(f"[SYNC] New: {len(new_ids)} | Existing: {len(existing_ids)} | Deleted: {len(deleted_ids)}")

    for document_id in new_ids | existing_ids:
        print(f"\n[SYNC] {source_files[document_id]}")
        index_document(str(source_files[document_id]))

    for document_id in deleted_ids:
        print(f"[SYNC] Removing: {document_id}")
        delete_document(document_id)

if __name__ == "__main__":
    sync_documents()