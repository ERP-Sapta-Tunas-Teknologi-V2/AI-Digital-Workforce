# RAG Chatbot API

API Retrieval-Augmented Generation (RAG) untuk melakukan pencarian dokumen dan menghasilkan jawaban berdasarkan knowledge base yang telah di-index.

## Daftar Isi

* [Stack](#stack)
* [Arsitektur](#arsitektur)
* [Requirements](#requirements)
* [Struktur Project](#struktur-project)
* [Setup Supabase](#setup-supabase)
* [Konfigurasi Environment](#konfigurasi-environment)
* [Instalasi](#instalasi)
* [Indexing Dokumen](#indexing-dokumen)
* [Sinkronisasi Dokumen](#sinkronisasi-dokumen)
* [Scheduler](#scheduler)
* [Menjalankan API](#menjalankan-api)
* [Testing](#testing)
* [Retrieval](#retrieval)
* [Session Management](#session-management)
* [Logging](#logging)
* [Deployment](#deployment)
* [Production Checklist](#production-checklist)
* [Dokumentasi](#dokumentasi)

---

## Stack

* Framework: Flask
* Database: Supabase
* Vector database: pgvector
* RAG framework: LangChain
* LLM runtime: Ollama
* LLM: Qwen2.5
* Embedding: BGE-M3
* Document processing: Docling
* Response: Server-Sent Events (SSE)

---

## Arsitektur

Pipeline indexing:

```text
Document
   ↓
Preprocessing
   ↓
Document Loader
   ↓
StructureAwareChunker
   ↓
Fingerprint
   ↓
BGE-M3 Embedding
   ↓
Supabase / pgvector
```

Pipeline retrieval:

```text
User Question
   ↓
BGE-M3 Embedding
   ↓
Hybrid Search
   ↓
Relevant Documents
   ↓
Qwen2.5
   ↓
SSE
   ↓
Frontend
```

Pipeline conversation:

```text
Session
   ↓
Conversation History
   ↓
Contextualizer
   ↓
Standalone Question
   ↓
Retrieval
   ↓
Qwen2.5
   ↓
SSE
```

---

## Requirements

Minimal:

```text
Python 3.x
Supabase
Ollama
Qwen2.5
BGE-M3
```

Instal Ollama mengikuti dokumentasi resmi [Ollama Quickstart](https://docs.ollama.com/quickstart).

Model yang digunakan:

```text
qwen2.5
bge-m3
```

Pull model:

```bash
ollama pull qwen2.5
ollama pull bge-m3
```

Verifikasi:

```bash
ollama list
```

---

## Struktur Project

```text
.
├── config/
│   └── settings.py
├── ingestion/
│   ├── cleaner.py
│   ├── indexer.py
│   ├── loader.py
│   └── splitter.py
├── insert/
│   ├── ingest.py
│   ├── scheduler.py
│   └── sync.py
├── rag/
│   ├── chain.py
│   ├── embeddings.py
│   ├── retriever.py
│   └── vectorstore.py
├── routes/
│   ├── chat.py
│   └── analytics.py
├── sync/
│   ├── export_logs.py
│   ├── retention.py
│   └── scheduler.py
├── utils/
│   ├── anonymizer.py
│   ├── extensions.py
│   ├── permissions.py
│   ├── query_logger.py
│   ├── supabase_admin.py
│   └── supabase_client.py
├── tests/
├── log/
├── docs/
├── .env
├── requirements.txt
├── supabase.sql
└── app.py
```

---

## Setup Supabase

### 1. Buat Project

1. Buka Supabase.
2. Pilih `Start your project`.
3. Pilih `New project`.
4. Isi konfigurasi:

```text
Project name: rag-chatbot
Database password: sesuai kebutuhan
Enable Data API: aktif
Automatically expose new tables: nonaktif
Enable automatic RLS: aktif
```

5. Klik `Create new project`.

### 2. Aktifkan pgvector

1. Buka `Database`.
2. Pilih `Extensions`.
3. Cari `vector`.
4. Aktifkan extension `vector`.
5. Gunakan schema default.

### 3. Ambil Credentials

Dari Supabase, siapkan:

```text
Project URL
Publishable key
Secret key
```

Secret key digunakan oleh backend dan tidak boleh diberikan kepada frontend.

---

## Konfigurasi Environment

Buat file:

```text
.env
```

Contoh:

```env
SUPABASE_URL=PROJECT-URL
SUPABASE_KEY=PUBLISHABLE-KEY
SUPABASE_SECRET_KEY=SECRET-KEY

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM=qwen2.5
LOCAL_EMB_MODEL=bge-m3
```

Nama variable harus disesuaikan dengan konfigurasi pada:

```text
config/settings.py
```

Jangan commit `.env` ke repository.

Tambahkan ke `.gitignore`:

```text
.env
.venv/
__pycache__/
log/
```

---

## Instalasi

Clone repository dan masuk ke directory project:

```bash
cd rag-chatbot
```

Buat virtual environment:

```bash
python -m venv .venv
```

Aktifkan virtual environment.

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Jika PowerShell memblokir script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Kemudian:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Inisialisasi Database

Buka:

```text
Supabase
→ SQL Editor
```

Jalankan isi:

```text
supabase.sql
```

Pastikan tabel dan function berhasil dibuat.

Tabel utama:

```text
documents
```

Struktur utama:

| Column        | Type         | Description            |
| ------------- | ------------ | ---------------------- |
| `id`          | bigint       | Primary key            |
| `content`     | text         | Isi chunk              |
| `metadata`    | jsonb        | Metadata chunk         |
| `document_id` | text         | Identitas dokumen      |
| `chunk_index` | int          | Index chunk            |
| `fingerprint` | text         | SHA-256 content        |
| `embedding`   | vector(1024) | BGE-M3 embedding       |
| `fts`         | tsvector     | Full-text search index |

Function utama:

```text
match_documents()
hybrid_search()
```

---

## Indexing Dokumen

Dokumen yang dapat di-index adalah:

- `.pdf`
- `.docx`

Dokumen diproses melalui:

```text
Document
   ↓
Preprocessing
   ↓
Chunking
   ↓
Fingerprint
   ↓
BGE-M3
   ↓
Supabase
```

Untuk melakukan indexing:

```bash
python ingest.py
```

Gunakan proses ini untuk indexing dokumen secara manual.

---

## Sinkronisasi Dokumen

Untuk melakukan sinkronisasi seluruh dokumen:

```bash
python sync.py
```

Synchronization membandingkan source dokumen dengan data yang terdapat di vector database.

Status dokumen:

```text
New
Existing
Deleted
```

Contoh output:

```text
New: 2 | Existing: 15 | Deleted: 1
```

Untuk dokumen `New` dan `Existing`, proses indexing dijalankan kembali.

Untuk dokumen yang sudah tidak terdapat pada source, seluruh embedding berdasarkan `document_id` dihapus.

---

## Scheduler

Scheduler digunakan untuk menjalankan synchronization dan cleanup secara otomatis.

### Konten Dinamis

Konten yang sering berubah dapat disinkronkan secara harian.

```text
Daily
01:00
→ sync
```

### Konten Statis

Konten yang relatif jarang berubah dapat disinkronkan secara mingguan.

```text
Weekly
Sunday 02:00
→ sync
```

### Retention Cleanup

Cleanup data expired dapat dijalankan secara berkala:

```text
Daily
02:00
→ retention cleanup
```

---

## Menjalankan API

Pastikan:

```text
.venv
.env
Supabase
Ollama
Qwen2.5
BGE-M3
```

telah dikonfigurasi.

Jalankan:

```bash
flask run --debug
```

Default API:

```text
http://127.0.0.1:5000
```

Root endpoint:

```http
GET /
```

Response:

```json
{
  "message": "RAG Service is running"
}
```

---

## Testing

Test berada pada:

```text
tests/
```

Menjalankan test tertentu:

```bash
pytest tests/[nama_file].py -v
```

Menjalankan seluruh test:

```bash
pytest -v
```

Area yang perlu diuji:

```text
API validation
Retrieval
Session
Rate limiting
CORS
Anonymization
Log export
```

---

## Retrieval

Retrieval menggunakan hybrid search yang menggabungkan:

```text
Semantic Search
+
Full-Text Search
```

Embedding menggunakan:

```text
BGE-M3
```

Flow:

```text
Question
   ↓
BGE-M3
   ↓
Hybrid Search
   ↓
Candidate Documents
   ↓
Relevant Documents
```

Tidak terdapat tahap reranking.

Konfigurasi retrieval utama:

| Parameter           | Value |
| ------------------- | ----: |
| Candidate documents |    10 |
| RRF k               |    50 |

---

## Session Management

Chatbot mendukung multi-turn conversation menggunakan session.

Policy:

| Parameter           | Value            |
| ------------------- | ---------------- |
| Idle timeout        | 30 menit         |
| Absolute timeout    | 24 jam           |
| Session ID          | UUID v4          |
| Development storage | In-memory        |
| Production storage  | Database / Redis |

Jika session expired:

```text
Expired Session
   ↓
Ignore old history
   ↓
Create new session
   ↓
Process request
```

Conversation history tidak digunakan setelah session expired.

Dokumentasi lengkap tersedia pada:

[`session.md`](docs/session.md)

---

## Logging

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

---

## CORS

Production hanya mengizinkan origin frontend yang telah masuk whitelist.

Production:

```text
https://saptatunas.com
```

Development:

```text
http://localhost:3000
```

Wildcard:

```text
*
```

tidak digunakan pada production.

CORS bukan authentication atau authorization.

Detail policy:

[`cors-policy.md`](docs/cors-policy.md)

---

## Rate Limiting

Endpoint chatbot menggunakan rate limit:

```text
10 request / menit / IP
```

Jika limit tercapai:

```text
HTTP 429
```

Request yang ditolak tidak menjalankan proses:

```text
Contextualizer
→ Embedding
→ Retrieval
→ LLM
```

Detail policy:

[`rate-limit-policy.md`](docs/rate-limit-policy.md)

---

## Log Export

Endpoint:

```text
GET /api/logs/export
```

Akses dibatasi untuk role:

```text
Marketing
Product
```

Filter tanggal menggunakan:

```text
start=YYYY-MM-DD
end=YYYY-MM-DD
```

Contoh:

```text
/api/logs/export?start=YYYY-MM-DD&end=YYYY-MM-DD
```

Export menggunakan CSV UTF-8 BOM.

---

## Deployment

Development menggunakan:

```text
Flask
+
Ollama
+
Qwen2.5
+
BGE-M3
```

Production sebaiknya menggunakan application server seperti:

```text
Gunicorn
```

Contoh:

```bash
gunicorn app:app
```

Jangan menggunakan Flask development server untuk production.

Architecture production:

```text
Frontend
   ↓
HTTPS
   ↓
Reverse Proxy / Load Balancer
   ↓
Gunicorn
   ↓
Flask
   ↓
RAG
   ├── Supabase
   ├── BGE-M3
   └── Qwen2.5 / Ollama
```

Jika Ollama dijalankan pada server production:

```text
Flask
   ↓
Ollama API
   ↓
Qwen2.5
```

Pastikan Ollama tidak diekspos langsung ke public internet tanpa network security yang sesuai.

### Production Environment

Gunakan environment variables untuk:

```text
SUPABASE_URL
SUPABASE_KEY
SUPABASE_SECRET_KEY
OLLAMA_BASE_URL
OLLAMA_LLM
LOCAL_EMB_MODEL
```

Debug mode harus dinonaktifkan:

```text
FLASK_DEBUG=0
```

Production harus menggunakan HTTPS.

---

## Production Checklist

### Database

```text
[ ] Supabase production project tersedia
[ ] pgvector aktif
[ ] supabase.sql sudah dijalankan
[ ] RLS dikonfigurasi
[ ] Backup tersedia
```

### Environment

```text
[ ] SUPABASE_SECRET_KEY dikonfigurasi
[ ] Secret tidak berada di repository
[ ] Debug mode disabled
[ ] Production environment terpisah dari development
```

### Ollama

```text
[ ] Ollama tersedia
[ ] Qwen2.5 tersedia
[ ] BGE-M3 tersedia
[ ] Model dapat diakses oleh application
[ ] Resource CPU/GPU mencukupi
```

### API

```text
[ ] Request validation aktif
[ ] Prompt injection validation aktif
[ ] SSE streaming berjalan
[ ] Fallback response berjalan
```

### Security

```text
[ ] HTTPS aktif
[ ] CORS whitelist production aktif
[ ] Wildcard CORS tidak digunakan
[ ] Rate limiting aktif
[ ] Role authorization untuk export aktif
[ ] Session isolation aktif
[ ] SUPABASE_SECRET_KEY tidak dikirim ke frontend
```

### Session

```text
[ ] Idle timeout 30 menit
[ ] Absolute timeout 24 jam
[ ] Expired session tidak menggunakan history
[ ] Production storage menggunakan Database / Redis
```

### Monitoring

```text
[ ] Query logging aktif
[ ] Retrieval latency logging aktif
[ ] LLM latency logging aktif
[ ] Error logging aktif
[ ] Retention cleanup aktif
```

---

## Performance

Development baseline:

| Metric     | Average |     P95 |
| ---------- | ------: | ------: |
| Retrieval  | 10.43 s | 10.99 s |
| LLM TTFT   | 22.25 s | 24.48 s |
| LLM Total  | 46.94 s | 58.92 s |
| End-to-End | 63.34 s | 78.40 s |

Baseline tersebut berasal dari environment development dan tidak digunakan sebagai production SLA.

Target production:

| Metric                   | Target |
| ------------------------ | -----: |
| Retrieval P95            |  ≤ 5 s |
| LLM TTFT P95             | ≤ 10 s |
| LLM Generation P95       | ≤ 30 s |
| End-to-End Streaming P95 | ≤ 45 s |

Detail:

[`performance-sla.md`](docs/performance-sla.md)

---

## Dokumentasi

Dokumentasi detail tersedia di directory [`docs/`](docs):

* [`api-contract.md`](docs/api-contract.md) — API contract dan frontend integration
* [`session.md`](docs/session.md) — session dan conversation management
* [`cors-policy.md`](docs/cors-policy.md) — CORS policy
* [`rate-limit-policy.md`](docs/rate-limit-policy.md) — rate limiting
* [`performance-sla.md`](docs/performance-sla.md) — performance baseline dan production SLA
* [`retention-policy.md`](docs/retention-policy.md) — data retention dan cleanup

---

## Project Flow

```text
                    INDEXING
                       │
                       ▼
                  Document
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
