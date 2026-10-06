# Logging

Query logging menggunakan anonymization sebelum data disimpan.

Data tertentu diganti dengan placeholder:

```text
Email → [EMAIL]
Phone → [PHONE]
Name  → [NAME]
```

Pola yang dikenali: email, nomor HP Indonesia (`08…`, `62…`, `+62…`), dan nama hanya jika didahului "nama saya" / "saya bernama".
Nama dalam bentuk lain tidak terdeteksi.

Retrieval logging:

```text
log/log_time.txt             → [request_id] [RETRIEVAL] embedding | embedding_tokens | search | rerank | relevant | total
                             → [request_id] [LLM] ttft | total, dan [REQUEST] total
                             → [request_id] [LOGGING] total (waktu insert interaction_logs)
log/log_retrieval-docs.txt   → pertanyaan (anonymized) dan seluruh rerank score (ditimpa setiap request)
log/log_rbac_audit.txt       → hanya ditulis bila RBAC filter aktif (saat ini nonaktif)
```

Metric retrieval:

```text
embedding
embedding_tokens
search
rerank
relevant
total
```

Metric `threshold` dihapus karena threshold rerank saat ini nonaktif.

Log digunakan untuk QA, monitoring, dan analisis latency.

## Ingestion Log

Setiap ingest dicatat ke tabel `ingestion_logs` (jumlah chunk inserted/updated/skipped/deleted/failed, durasi, `parse_error`).

## Feedback

Setiap jawaban chatbot dapat diberi feedback melalui:

```http
POST /api/feedback
```

Feedback (`up`/`down` beserta alasan opsional) terhubung ke jawaban dan dokumen yang dirujuk melalui `request_id`, sehingga dapat digunakan untuk mengidentifikasi jawaban bermasalah dan dokumen yang perlu direvisi (lihat [`analytics-endpoints.md`](../api-operasional/analytics-endpoints.md)).

Detail request/response endpoint `/api/feedback` tersedia pada [`api-contract.md`](../api-operasional/api-contract.md).

## Export

CSV hasil export (`GET /api/logs/export`) berisi kolom `id, query, timestamp`.

## Data Retention

Retensi seluruh data log (interaction logs, feedback, session) mengikuti [`retention-policy.md`](../kebijakan/retention-policy.md).
