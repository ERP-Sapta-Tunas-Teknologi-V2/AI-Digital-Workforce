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
                  MinIO        MinIO
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
                  Session
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
                 Qwen2.5
                    │
                    ▼
                    SSE
                    │
                    ▼
                 Frontend
```
