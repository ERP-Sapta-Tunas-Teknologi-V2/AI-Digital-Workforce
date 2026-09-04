from sentence_transformers import CrossEncoder

from config.settings import RERANKER_MODEL
reranker = CrossEncoder(RERANKER_MODEL, max_length=8192)

def rerank(question, documents, top_k=3):
    if not documents:
        return []

    pairs = [(question, document.page_content) for document in documents]
    scores = reranker.predict(pairs, show_progress_bar=False)
    ranked = sorted(zip(documents, scores), key=lambda x: float(x[1]), reverse=True)

    results = []

    for document, score in ranked[:top_k]:
        document.metadata["rerank_score"] = float(score)
        results.append(document)

    return results