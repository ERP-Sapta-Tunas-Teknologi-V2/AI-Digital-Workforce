import time

from settings import EMBEDDING_MODEL
from rag.embeddings import embeddings, count_embedding_tokens
from utils.supabase_client import supabase
from utils.logger import log_index_usage

TARGET_BATCH_TOKENS = 9_000
MAX_RETRIES = 3

def _count_tokens(text):
    return count_embedding_tokens(text)

def _create_batches(items):
    batches = []
    current_batch = []
    current_tokens = 0

    for item in items:
        text = item["chunk"].page_content
        tokens = _count_tokens(text)

        if tokens > TARGET_BATCH_TOKENS:
            print(
                f"Warning: chunk contains {tokens:,} tokens, "
                f"larger than target batch size {TARGET_BATCH_TOKENS:,}."
            )

        if current_batch and current_tokens + tokens > TARGET_BATCH_TOKENS:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(item)
        current_tokens += tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def _embed_batch(texts, batch_number):
    token_count = count_embedding_tokens(texts)

    print(
        f"Embedding batch {batch_number} | "
        f"chunks={len(texts)} | tokens={token_count:,}"
    )

    for attempt in range(MAX_RETRIES + 1):
        try:
            print(
                f"Sending batch {batch_number} to Ollama..."
            )

            vectors = embeddings.embed_documents(texts)

            print(
                f"Batch {batch_number} completed."
            )

            return vectors, token_count

        except (TimeoutError, ConnectionError) as e:
            if attempt == MAX_RETRIES:
                print(
                    f"Network error: batch {batch_number} "
                    f"failed: {e}"
                )
                return None, 0

            wait_time = 10

            print(
                f"Network error. Retrying in {wait_time}s..."
            )

            time.sleep(wait_time)

        except Exception as e:
            print(
                f"Embedding error on batch {batch_number}: "
                f"{type(e).__name__}: {e}"
            )
            return None, 0

    return None, 0


def add_documents(chunks):
    inserted = 0
    updated = 0
    skipped = 0
    failed = 0
    deleted = 0

    failed_chunks = []
    total_embedding_tokens = 0

    if not chunks:
        print("No chunks to process.")

        return {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "deleted": 0,
            "failed_chunks": []
        }

    document_id = chunks[0].metadata["document_id"]
    pending = []

    for chunk in chunks:
        metadata = chunk.metadata.copy()

        chunk_document_id = metadata.pop("document_id")
        chunk_index = metadata.pop("chunk_index")
        fingerprint = metadata.pop("fingerprint")

        if chunk_document_id != document_id:
            raise ValueError(
                "All chunks must belong to the same document."
            )

        existing = (
            supabase
            .table("documents")
            .select("id, fingerprint")
            .eq("document_id", document_id)
            .eq("chunk_index", chunk_index)
            .limit(1)
            .execute()
        )

        if (
            existing.data
            and existing.data[0]["fingerprint"] == fingerprint
        ):
            skipped += 1
            continue

        pending.append({
            "chunk": chunk,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "fingerprint": fingerprint,
            "metadata": metadata,
            "existing_id": (
                existing.data[0]["id"]
                if existing.data
                else None
            )
        })

    batches = _create_batches(pending)

    print(
        f"New/changed chunks: {len(pending)} | "
        f"Batches: {len(batches)} | "
        f"Skipped: {skipped} | "
        f"Target batch tokens: {TARGET_BATCH_TOKENS:,}"
    )

    for batch_number, batch in enumerate(batches, start=1):
        texts = [
            item["chunk"].page_content
            for item in batch
        ]

        vectors, batch_tokens = _embed_batch(
            texts,
            batch_number
        )

        if vectors is None:
            failed += len(batch)
            failed_chunks.extend(batch)

            print(
                f"Batch {batch_number} failed. "
                f"Skipping {len(batch)} chunks."
            )

            continue

        total_embedding_tokens += batch_tokens

        if len(vectors) != len(batch):
            failed += len(batch)
            failed_chunks.extend(batch)

            print(
                f"Batch {batch_number} returned "
                f"{len(vectors)} vectors for {len(batch)} chunks."
            )

            continue

        rows = []

        for item, vector in zip(batch, vectors):
            rows.append({
                "content": item["chunk"].page_content,
                "metadata": item["metadata"],
                "document_id": item["document_id"],
                "chunk_index": item["chunk_index"],
                "fingerprint": item["fingerprint"],
                "embedding": vector
            })

        try:
            (
                supabase
                .table("documents")
                .upsert(
                    rows,
                    on_conflict="document_id,chunk_index"
                )
                .execute()
            )

            for item in batch:
                if item["existing_id"]:
                    updated += 1
                else:
                    inserted += 1

            print(
                f"Upserted batch {batch_number}: "
                f"{len(batch)} chunks"
            )

        except Exception as e:
            failed += len(batch)
            failed_chunks.extend(batch)

            print(
                f"Supabase upsert failed for batch "
                f"{batch_number}: "
                f"{type(e).__name__}: {e}"
            )

    # Jangan hapus stale chunks jika ada kegagalan.
    if failed == 0:
        current_chunk_indexes = [
            chunk.metadata["chunk_index"]
            for chunk in chunks
        ]

        existing_rows = (
            supabase
            .table("documents")
            .select("id, chunk_index")
            .eq("document_id", document_id)
            .execute()
        )

        stale_ids = [
            row["id"]
            for row in existing_rows.data or []
            if row["chunk_index"] not in current_chunk_indexes
        ]

        if stale_ids:
            try:
                (
                    supabase
                    .table("documents")
                    .delete()
                    .in_("id", stale_ids)
                    .execute()
                )

                deleted = len(stale_ids)

                print(
                    f"Deleted stale chunks: {deleted}"
                )

            except Exception as e:
                print(
                    f"Failed to delete stale chunks: "
                    f"{type(e).__name__}: {e}"
                )

    else:
        print(
            f"Skipping stale deletion because "
            f"{failed} chunks failed."
        )

    print(
        f"Inserted: {inserted} | "
        f"Updated: {updated} | "
        f"Skipped: {skipped} | "
        f"Failed: {failed} | "
        f"Deleted: {deleted} | "
        f"Embedding tokens: {total_embedding_tokens:,}"
    )

    if failed_chunks:
        print("\nFailed chunks:")

        for item in failed_chunks:
            print(
                f"FAILED | "
                f"document_id={item['document_id']} | "
                f"chunk_index={item['chunk_index']} | "
                f"fingerprint={item['fingerprint']}"
            )

    if total_embedding_tokens > 0:
        log_index_usage(
            emb_model=EMBEDDING_MODEL,
            embedding_tokens=total_embedding_tokens
        )

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "deleted": deleted,
        "failed_chunks": failed_chunks
    }


def get_document_ids():
    result = (
        supabase
        .table("documents")
        .select("document_id")
        .execute()
    )

    return {
        row["document_id"]
        for row in result.data or []
    }


def delete_document(document_id):
    (
        supabase
        .table("documents")
        .delete()
        .eq("document_id", document_id)
        .execute()
    )

    print(
        f"Deleted document: {document_id}"
    )