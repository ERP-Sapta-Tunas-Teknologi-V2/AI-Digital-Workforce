from langchain_ollama import OllamaEmbeddings
from transformers import AutoTokenizer
from functools import lru_cache
from config import OLLAMA_BASE_URL, EMBEDDING_MODEL, EMBEDDING_TOKENIZER

embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)

@lru_cache(maxsize=1)
def get_tokenizer():
    return AutoTokenizer.from_pretrained(EMBEDDING_TOKENIZER)

def count_embedding_tokens(text: str) -> int:
    return len(get_tokenizer().encode(text, add_special_tokens=True))