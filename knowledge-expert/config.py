import os
from dotenv import load_dotenv

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_LLM = os.getenv("OLLAMA_LLM")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
RERANKER_MODEL = os.getenv("RERANKER_MODEL")
VISION_MODEL = os.getenv("VISION_MODEL")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "documents")