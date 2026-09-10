from pathlib import Path
from datetime import datetime
import tempfile

from ingestion.cleaner import preprocessing
from ingestion.loader import load_markdown, load_document
from ingestion.splitter import StructureAwareChunker
from ingestion.vectorstore import add_documents
from utils.status_tracker import set_status
from utils.minio_client import client, object_key
import config

chunker = StructureAwareChunker(max_tokens=1000)

def index_document(category: str, filename: str):
    document_id = f"{category}:{Path(filename).stem}"
    uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        set_status(document_id, filename, category, "processing")

        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / filename

            client.fget_object(
                config.MINIO_BUCKET,
                object_key(category, filename),
                str(local_path)
            )

            if local_path.suffix.lower() in {".docx", ".pdf"}:
                print(f'Cleaning document...')
                markdown = preprocessing(local_path)
                print("Cleaned.")

                print(f"Loading document...")
                documents = load_markdown(markdown)
                print("Loaded.")

                print("Creating chunks...")
                chunks = chunker.split_markdown(documents, filename, document_id, category)
                print(f"Created {len(chunks)} chunks.")

            else:
                print(f"Loading document...")
                documents = load_document(str(local_path))
                print("Loaded.")

                print("Creating chunks...")
                chunks = chunker.split_docling(documents, filename, document_id, category)
                print(f"Created {len(chunks)} chunks.")

        print("Adding documents...")
        result = add_documents(chunks)

        if result["failed"]:
            print("Some chunks failed to process.")
            set_status(document_id, filename, category, "failed", detail=f"{result['failed']} chunks failed")
        else:
            print("Documents successfully added.")
            set_status(document_id, filename, category, "success")

    except Exception as e:
        print(f"[INDEX] failed for {document_id}: {type(e).__name__}: {e}")
        set_status(document_id, filename, category, "failed", detail=str(e))
        raise