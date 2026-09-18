# Logging

Query logging menggunakan anonymization sebelum data disimpan.

Data tertentu diganti dengan placeholder:

```text
Email → [EMAIL]
Phone → [PHONE]
Name  → [NAME]
```

Retrieval logging:

```text
log/log_retrieval-time.txt
log/log_retrieval-docs.txt
```

Metric retrieval:

```text
embedding
search
relevant
total
```

Log digunakan untuk QA, monitoring, dan analisis latency.

## Feedback

Setiap jawaban chatbot dapat diberi feedback melalui:

```http
POST /api/feedback
```

Feedback (`up`/`down` beserta alasan opsional) terhubung ke jawaban dan dokumen yang dirujuk melalui `request_id`, sehingga dapat digunakan untuk mengidentifikasi jawaban bermasalah dan dokumen yang perlu direvisi (lihat [`analytics-endpoints.md`](../api-operasional/analytics-endpoints.md)).

Detail request/response endpoint `/api/feedback` tersedia pada [`api-contract.md`](../api-operasional/api-contract.md).

## Data Retention

Retensi seluruh data log (interaction logs, feedback, session) mengikuti [`retention-policy.md`](../kebijakan/retention-policy.md).
