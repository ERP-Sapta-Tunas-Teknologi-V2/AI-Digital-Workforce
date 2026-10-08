from langchain_ollama import ChatOllama
from config import OLLAMA_BASE_URL, OLLAMA_LLM, OLLAMA_NUM_CTX, OLLAMA_KEEP_ALIVE

def get_llm(model=None, **overrides):
    params = {
        "model": model or OLLAMA_LLM,
        "base_url": OLLAMA_BASE_URL,
        "temperature": 0,
        "num_ctx": OLLAMA_NUM_CTX,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "reasoning": False
    }
    return ChatOllama(**{**params, **overrides})