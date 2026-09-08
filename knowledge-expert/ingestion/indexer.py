from pathlib import Path
from datetime import datetime

from ingestion.cleaner import preprocessing
from ingestion.loader import load_markdown, load_document
from ingestion.splitter import StructureAwareChunker
from ingestion.vectorstore import add_documents

chunker = StructureAwareChunker(max_tokens=1000)

def index_document(file_path: str):
    path = Path(file_path)

    category = path.parent.name
    source = path.name
    document_id = f"{category}:{path.stem}"
    uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if path.suffix.lower() in {".docx", ".pdf"}:
        print(f'Cleaning document...')
        markdown = preprocessing(path)
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
    if result["failed"]: print("Some chunks failed to process.")
    else: print("Documents successfully added.")