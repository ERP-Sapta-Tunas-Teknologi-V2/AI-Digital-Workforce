import os
from dotenv import load_dotenv

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_LLM = os.getenv("OLLAMA_LLM")
LOCAL_EMB_MODEL = os.getenv("LOCAL_EMB_MODEL")

RERANKER_MODEL = os.getenv("RERANKER_MODEL")

VOYAGE_KEY = os.getenv("VOYAGE_KEY")
VOYAGE_EMB_MODEL = os.getenv("VOYAGE_EMB_MODEL")

ARK_API_KEY = os.getenv("ARK_API_KEY")
ARK_BASE_URL = os.getenv("ARK_BASE_URL")
ARK_LLM = os.getenv("ARK_LLM")

SYNTHORAI_API_KEY = os.getenv("SYNTHORAI_API_KEY")