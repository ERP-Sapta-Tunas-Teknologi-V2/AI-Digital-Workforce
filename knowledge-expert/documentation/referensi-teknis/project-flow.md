# Project Flow

```text
                    DOCUMENT MANAGEMENT
                           │
                           ▼
                      Dashboard
                           │
                    ┌──────┴──────┐
                    │             │
                  Upload        Delete
                    │             │
                    ▼             ▼
       Screening (duplikat /    MinIO
       rahasia / usang)
                    │
                    ▼
                  MinIO
                    │
                    │ Ingest
                    ▼
                 Download
                    │
                    ▼
               Preprocessing
                    │
                    ▼
            StructureAwareChunker
                    │
                    ▼
                Fingerprint
                    │
                    ▼
                  BGE-M3
                    │
                    ▼
              Supabase/pgvector
                    │
                    ▼
              document_status
                    │
                    │
                    ▼
                   RUNTIME
                    │
                    ▼
                User Request
                    │
                    ▼
        Validasi (panjang + injection)
                    │
                    ▼
                  Session
                    │
                    ▼
                Anonymizer
                    │
                    ▼
              Contextualizer
                    │
                    ▼
                 BGE-M3
                    │
                    ▼
               Hybrid Search
                    │
                    ▼
        Reranker (Qwen3-Reranker, top 3)
                    │
                    ▼
                 Qwen2.5
                    │
                    ▼
                    SSE
                    │
                    ▼
                 Frontend
```
