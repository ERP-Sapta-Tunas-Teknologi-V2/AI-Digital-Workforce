import os
os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["TORCH_COMPILE_DISABLE"] = "1"

from ingestion.indexer import index_document

if __name__ == "__main__":
    file_path = "path/to/file"
    print(f'Indexing "{file_path}"...')
    index_document(file_path)