import os
os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["TORCH_COMPILE_DISABLE"] = "1"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import sys
from ingestion.indexer import index_document

if __name__ == "__main__":
    category, filename = sys.argv[1], sys.argv[2]
    print(f'Indexing "{category}/{filename}"...')
    index_document(category, filename)