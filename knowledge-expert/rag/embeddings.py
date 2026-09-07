from langchain_ollama import OllamaEmbeddings
from transformers import AutoTokenizer

from settings import OLLAMA_BASE_URL, EMBEDDING_MODEL
embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)

tokenizer = AutoTokenizer.from_pretrained(f"BAAI/{EMBEDDING_MODEL}")
def count_embedding_tokens(text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=True))