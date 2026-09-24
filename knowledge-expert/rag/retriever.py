from langchain_core.documents import Document
import time
import re

from rag.embeddings import embeddings, count_embedding_tokens
from rag.reranker import rerank
from utils.supabase_client import supabase
from utils.anonymizer import anonymize_query

# RERANK_THRESHOLD = 0.0

RETRIEVAL_STOPWORDS = {
    "?",

    # Indonesian
    "apa", "apakah", "berapa", "siapa", "dimana", "di mana", "mana",
    "kapan", "mengapa", "kenapa", "bagaimana", "dan", "dari",
    "tolong", "mohon", "bisa", "dapatkah", "ini", "itu", "yang",

    # English
    "what", "is", "are", "do", "does", "did",
    "how", "why", "when", "where", "who", "of",
    "which", "can", "could", "would", "should",
    "please", "this", "that", "which", "and"
}

def clean_retrieval_query(question):
    words = question.split()
    words = [w for w in words if w.lower().strip("?!.,") not in RETRIEVAL_STOPWORDS]
    return " ".join(words)

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

    retrieval_question = clean_retrieval_query(question)
    print("retrieval_question:", retrieval_question)

    embedding_tokens = count_embedding_tokens(question)
    query_embedding = embeddings.embed_query(question)

    embedding_time = time.perf_counter() - embedding_start
    search_start = time.perf_counter()

    result = supabase.rpc("hybrid_search", {
        "query_text": retrieval_question,
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
        metadata["rank_fulltext"] = row.get("rank_fulltext")
        metadata["rank_semantic"] = row.get("rank_semantic")

        document = Document(page_content=row["content"], metadata=metadata)
        documents.append(document)

    rerank_start = time.perf_counter()

    all_scored = rerank(question, documents, top_k=len(documents))
    with open("log/log_retrieval-docs.txt", "a", encoding="utf-8") as f:
        f.write("\n\n=== RERANK SCORES (ALL) ===\n")
        for document in all_scored:
            f.write(
                f"score={document.metadata['rerank_score']:.4f} | "
                f"fulltext_rank={document.metadata.get('rank_fulltext')} | "
                f"semantic_rank={document.metadata.get('rank_semantic')} | "
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

    context_parts = []
    for i, document in enumerate(documents, 1):
        context_parts.append(
            f"[{i}]\n"
            f"{document.page_content}\n"
            f"(tanggal efektif: {document.metadata.get('uploaded_at', '')[:10]})"
        )
    context = "\n\n".join(context_parts)

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

    return documents, context