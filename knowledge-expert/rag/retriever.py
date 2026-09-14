from langchain_core.documents import Document
import time
import re

from rag.embeddings import embeddings, count_embedding_tokens
from rag.reranker import rerank
from utils.supabase_client import supabase
from utils.anonymizer import anonymize_query
from config import EMBEDDING_MODEL

# RERANK_THRESHOLD = 0.0

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
    role: str = None,
    allowed_categories: list[str] | None = None,
    candidate_k: int = 30,
    rerank_k: int = 3
) -> tuple[list[Document], str, int]:

    start = time.perf_counter()
    embedding_start = time.perf_counter()

    expanded_question = expand_query(question)
    print("expanded_question:", expanded_question)

    embedding_model = EMBEDDING_MODEL
    embedding_tokens = count_embedding_tokens(question)
    query_embedding = embeddings.embed_query(question)

    embedding_time = time.perf_counter() - embedding_start
    search_start = time.perf_counter()

    result = supabase.rpc("hybrid_search", {
        "query_text": expanded_question,
        "query_embedding": query_embedding,
        "match_count": candidate_k,
        "rrf_k": 10,
        "category_filter": allowed_categories,
    }).execute()

    search_time = time.perf_counter() - search_start

    if allowed_categories is not None:
        with open("log/log_rbac_audit.txt", "a", encoding="utf-8") as f:
            f.write(
                f"[{request_id}] RBAC_FILTER_APPLIED | "
                f"role={role} | "
                f"allowed_categories={allowed_categories} | "
                f"candidates_returned={len(result.data or [])}\n"
            )

    documents = []

    safe_query = anonymize_query(question)

    with open("log/log_retrieval-docs.txt", "w", encoding="utf-8") as f:
        f.write(f"\n\n=== REQUEST {request_id} ===\nQUESTION: {safe_query}\n")

    for row in result.data or []:
        metadata = row.get("metadata") or {}
        metadata["retrieval_score"] = row["hybrid_score"]
        metadata["chunk_index"] = row.get("chunk_index")
        metadata["content"] = row.get("content")

        document = Document(page_content=row["content"], metadata=metadata)
        documents.append(document)

    rerank_start = time.perf_counter()

    all_scored = rerank(question, documents, top_k=len(documents))
    with open("log/log_retrieval-docs.txt", "a", encoding="utf-8") as f:
        f.write("\n\n=== RERANK SCORES (ALL) ===\n")
        for document in all_scored:
            f.write(
                f"score={document.metadata['rerank_score']:.4f} | "
                f"section={document.metadata.get('section_title')!r} | "
                f"source={document.metadata.get('source')} | "
                f"page={document.metadata.get('page')}\n"
            )
    documents = all_scored[:rerank_k]

    rerank_time = time.perf_counter() - rerank_start

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
        f"rerank={rerank_time:.3f}s | "
        # f"threshold={RERANK_THRESHOLD:.4f} | "
        f"relevant={len(documents)} | "
        f"total={total_time:.3f}s\n"
    )
    with open("log/log_time.txt", "a", encoding="utf-8") as f:
        f.write(log)

    return documents, context, embedding_tokens, embedding_model