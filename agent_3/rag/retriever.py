from langchain_core.documents import Document
import time
import re

from rag.embeddings import (
    embeddings, count_embedding_tokens,  # Ollama
    # get_embedding_tokens, embed_query_with_usage, client  # Voyage
)
from rag.reranker import rerank
from utils.supabase_client import supabase
from utils.anonymizer import anonymize_query
from config.settings import LOCAL_EMB_MODEL, VOYAGE_EMB_MODEL

# RERANK_THRESHOLD = 3.0

STT_WORDS = {"stt", "sapta", "tunas", "teknologi"}
STT_GROUP = "(stt|sapta<->tunas<->teknologi)"

def expand_query(query):
    lowered = query.lower()
    raw_tokens = re.findall(r"\w+", lowered)

    non_stt_tokens = [t for t in raw_tokens if t not in STT_WORDS]
    has_stt = len(non_stt_tokens) < len(raw_tokens)

    parts = non_stt_tokens.copy()
    if has_stt:
        parts.append(STT_GROUP)

    return " ".join(parts)

def hybrid_retrieve(
    question: str,
    request_id: str,
    candidate_k: int = 5,
    rerank_k: int = 3
) -> tuple[list[Document], str, int]:

    start = time.perf_counter()
    embedding_start = time.perf_counter()

    # expanded_question = question
    expanded_question = expand_query(question)
    print(expanded_question)

    # Ollama
    embedding_model = LOCAL_EMB_MODEL
    embedding_tokens = count_embedding_tokens(question)
    query_embedding = embeddings.embed_query(question)

    # Voyage
    # embedding_model = VOYAGE_EMB_MODEL
    # query_embedding = embed_query_with_usage(question)
    # embedding_tokens = get_embedding_tokens()

    embedding_time = time.perf_counter() - embedding_start
    search_start = time.perf_counter()

    result = supabase.rpc("hybrid_search", {
        "query_text": expanded_question,
        "query_embedding": query_embedding,
        "match_count": candidate_k,
        "rrf_k": 10,
    }).execute()

    search_time = time.perf_counter() - search_start

    documents = []

    safe_query = anonymize_query(question)

    with open("log/log_retrieval-docs.txt", "w", encoding="utf-8") as f:
        f.write(f"\n\n=== REQUEST {request_id} ===\nQUESTION: {safe_query}\n")

    for row in result.data or []:
        metadata = row.get("metadata") or {}
        metadata["retrieval_score"] = row["hybrid_score"]

        document = Document(page_content=row["content"], metadata=metadata)
        documents.append(document)

    # rerank_start = time.perf_counter()

    # all_scored = rerank(question, documents, top_k=len(documents))
    # with open("log/log_retrieval-docs.txt", "a", encoding="utf-8") as f:
    #     f.write("\n\n=== RERANK SCORES (ALL) ===\n")
    #     for document in all_scored:
    #         f.write(
    #             f"score={document.metadata['rerank_score']:.4f} | "
    #             f"section={document.metadata.get('section_title')!r} | "
    #             f"source={document.metadata.get('source')} | "
    #             f"page={document.metadata.get('page')}\n"
    #         )
    # documents = all_scored[:rerank_k]

    # rerank_time = time.perf_counter() - rerank_start

    documents = [
        document
        for document in documents
        # if document.metadata["rerank_score"] >= RERANK_THRESHOLD
    ]

    context = "\n\n".join(document.page_content for document in documents)

    total_time = time.perf_counter() - start

    log = (
        f"[{request_id}] question='{safe_query}'\n"
        f"[{request_id}] [RETRIEVAL] "
        f"embedding={embedding_time:.3f}s | "
        f"embedding_tokens={embedding_tokens} | "
        f"search={search_time:.3f}s | "
        # f"rerank={rerank_time:.3f}s | "
        # f"threshold={RERANK_THRESHOLD:.4f} | "
        f"relevant={len(documents)} | "
        f"total={total_time:.3f}s\n"
    )
    with open("log/log_time.txt", "a", encoding="utf-8") as f:
        f.write(log)

    return documents, context, embedding_tokens, embedding_model