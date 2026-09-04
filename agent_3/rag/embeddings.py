from langchain_ollama import OllamaEmbeddings
from transformers import AutoTokenizer
from config.settings import OLLAMA_BASE_URL, LOCAL_EMB_MODEL
embeddings = OllamaEmbeddings(model=LOCAL_EMB_MODEL, base_url=OLLAMA_BASE_URL)
tokenizer = AutoTokenizer.from_pretrained(f"BAAI/{LOCAL_EMB_MODEL}")
def count_embedding_tokens(text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=True))

# import voyageai
# from langchain_voyageai import VoyageAIEmbeddings
# from config.settings import VOYAGE_KEY, VOYAGE_EMB_MODEL

# embeddings = VoyageAIEmbeddings(voyage_api_key=VOYAGE_KEY, model=VOYAGE_EMB_MODEL, output_dimension=1024, truncation=False)
# client = voyageai.Client(api_key=VOYAGE_KEY)

# last_usage = {"total_tokens": 0}

# def count_embedding_tokens(texts):
#     if isinstance(texts, str): texts = [texts]
#     return client.count_tokens(texts, model=VOYAGE_EMB_MODEL)

# def embed_query_with_usage(text):
#     result = client.embed(
#         [text],
#         model=VOYAGE_EMB_MODEL,
#         input_type="query",
#         output_dimension=1024,
#         truncation=False
#     )
#     last_usage["total_tokens"] = result.total_tokens
#     return result.embeddings[0]

# def embed_text_with_usage(texts):
#     if isinstance(texts, str): texts = [texts]
#     result = client.embed(
#         texts,
#         model=VOYAGE_EMB_MODEL,
#         input_type="document",
#         output_dimension=1024,
#         truncation=False
#     )
#     last_usage["total_tokens"] = result.total_tokens
#     return result.embeddings

# def get_embedding_tokens():
#     return last_usage["total_tokens"]