import time
import voyageai

from config.settings import VOYAGE_EMB_MODEL
from rag.embeddings import (
    embeddings, count_embedding_tokens,  # Ollama
    # count_embedding_tokens, embed_text_with_usage  # Voyage
)
from utils.supabase_client import supabase
from utils.logger import log_index_usage

MAX_RPM = 3
MAX_TPM = 10_000
TARGET_BATCH_TOKENS = 9_000
MAX_RETRIES = 3
USE_VOYAGE = False

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
                f"larger than target batch size "
                f"{TARGET_BATCH_TOKENS:,}."
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

class VoyageRateLimiter:
    def __init__(self, max_rpm=MAX_RPM, max_tpm=MAX_TPM):
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.history = []

    def _cleanup(self):
        now = time.time()

        self.history = [
            (timestamp, tokens)
            for timestamp, tokens in self.history
            if now - timestamp < 60
        ]

    def wait(self, tokens):
        while True:
            self._cleanup()

            now = time.time()
            request_count = len(self.history)
            token_count = sum(
                tokens for _, tokens in self.history
            )

            rpm_exceeded = request_count >= self.max_rpm
            tpm_exceeded = (
                token_count + tokens > self.max_tpm
            )

            if not rpm_exceeded and not tpm_exceeded:
                return

            wait_time = 1

            if self.history:
                oldest_timestamp = self.history[0][0]

                wait_time = max(
                    wait_time,
                    60 - (now - oldest_timestamp)
                )

            reasons = []

            if rpm_exceeded:
                reasons.append(
                    f"RPM {request_count}/{self.max_rpm}"
                )

            if tpm_exceeded:
                reasons.append(
                    f"TPM {token_count:,}+{tokens:,}/"
                    f"{self.max_tpm:,}"
                )

            print(
                f"[RATE LIMIT] {', '.join(reasons)}. "
                f"Waiting {wait_time:.1f}s..."
            )

            time.sleep(wait_time)

    def record(self, tokens):
        self.history.append(
            (time.time(), tokens)
        )


def _embed_batch(texts, batch_number, rate_limiter):
    token_count = count_embedding_tokens(texts)

    print(
        f"Embedding batch {batch_number} | "
        f"chunks={len(texts)} | "
        f"tokens={token_count:,}"
    )

    if USE_VOYAGE and token_count > MAX_TPM:
        raise ValueError(
            f"Batch {batch_number} contains "
            f"{token_count:,} tokens, exceeding "
            f"MAX_TPM={MAX_TPM:,}."
        )

    for attempt in range(MAX_RETRIES + 1):
        try:
            if USE_VOYAGE:
                rate_limiter.wait(token_count)

            print(
                f"Sending batch {batch_number} "
                f"to {'Voyage' if USE_VOYAGE else 'Ollama'}..."
            )

            vectors = embeddings.embed_documents(texts)  # Ollama
            # vectors = embed_text_with_usage(texts)  # Voyage

            if USE_VOYAGE:
                rate_limiter.record(token_count)

            print(
                f"Batch {batch_number} completed."
            )

            return vectors, token_count

        except voyageai.error.RateLimitError as e:
            if attempt == MAX_RETRIES:
                print(
                    f"Rate limit: batch "
                    f"{batch_number} failed: {e}"
                )
                return None, 0

            wait_time = 60

            print(
                f"Rate limit. "
                f"Retrying in {wait_time}s..."
            )

            time.sleep(wait_time)

        except (TimeoutError, ConnectionError) as e:
            if attempt == MAX_RETRIES:
                print(
                    f"Network error: batch "
                    f"{batch_number} failed: {e}"
                )
                return None, 0

            wait_time = 60

            print(
                f"Network error. "
                f"Retrying in {wait_time}s..."
            )

            time.sleep(wait_time)

        except Exception as e:
            print(
                f"Embedding error on batch "
                f"{batch_number}: "
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

        chunk_document_id = metadata.pop(
            "document_id"
        )

        chunk_index = metadata.pop(
            "chunk_index"
        )

        fingerprint = metadata.pop(
            "fingerprint"
        )

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
            and existing.data[0]["fingerprint"]
            == fingerprint
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
        f"Target batch tokens: "
        f"{TARGET_BATCH_TOKENS:,}"
    )

    rate_limiter = VoyageRateLimiter(
        max_rpm=MAX_RPM,
        max_tpm=MAX_TPM
    )

    for batch_number, batch in enumerate(
        batches,
        start=1
    ):
        texts = [
            item["chunk"].page_content
            for item in batch
        ]

        vectors, batch_tokens = _embed_batch(
            texts,
            batch_number,
            rate_limiter
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
                f"{len(vectors)} vectors for "
                f"{len(batch)} chunks."
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
                f"Supabase upsert failed for "
                f"batch {batch_number}: "
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
            if row["chunk_index"]
            not in current_chunk_indexes
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
        f"Embedding tokens: "
        f"{total_embedding_tokens:,}"
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
            emb_model=VOYAGE_EMB_MODEL,
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