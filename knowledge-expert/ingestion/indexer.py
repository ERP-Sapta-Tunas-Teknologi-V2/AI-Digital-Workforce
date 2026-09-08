from pathlib import Path
from datetime import datetime

from ingestion.cleaner import preprocessing
from ingestion.loader import load_markdown, load_document
from ingestion.splitter import StructureAwareChunker
from ingestion.vectorstore import add_documents
from utils.status_tracker import set_status

chunker = StructureAwareChunker(max_tokens=1000)

def index_document(file_path: str):
    path = Path(file_path)

    category = path.parent.name
    source = path.name
    document_id = f"{category}:{path.stem}"
    uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        set_status(document_id, source, category, "processing")

        if path.suffix.lower() in {".docx", ".pdf"}:
            print(f'Cleaning document...')
            markdown = preprocessing(path, document_id)
            print("Cleaned.")

            print(f"Loading document...")
            documents = load_markdown(markdown)
            print("Loaded.")

            print("Creating chunks...")
            chunks = chunker.split_markdown(documents, source, document_id, category, uploaded_at)
            print(f"Created {len(chunks)} chunks.")

        else:
            print(f"Loading document...")
            documents = load_document(file_path)
            print("Loaded.")

            print("Creating chunks...")
            chunks = chunker.split_docling(documents, source, document_id, category, uploaded_at)
            print(f"Created {len(chunks)} chunks.")

        print("Adding documents...")
        result = add_documents(chunks)

        if result["failed"]:
            print("Some chunks failed to process.")
            set_status(document_id, source, category, "failed", detail=f"{result['failed']} chunks failed")
        else:
            print("Documents successfully added.")
            set_status(document_id, source, category, "success")

    except Exception as e:
        print(f"[INDEX] failed for {document_id}: {type(e).__name__}: {e}")
        set_status(document_id, source, category, "failed", detail=str(e))
        raise