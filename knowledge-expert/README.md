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
* [Admin Endpoints](#admin-endpoints)
* [Menjalankan API](#menjalankan-api)
* [Testing](#testing)
* [Retrieval](#retrieval)
* [Session Management](#session-management)
* [Logging](#logging)
* [CORS](#cors)
* [Rate Limiting](#rate-limiting)
* [Log Export](#log-export)
* [Analytics Endpoints](#analytics-endpoints)
* [Deployment](#deployment)
* [Production Checklist](#production-checklist)
* [Performance](#performance)
* [Dokumentasi](#dokumentasi)
* [Project Flow](#project-flow)

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
* Distributed lock: Redis

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

```text
Python 3.x
Supabase
Ollama
Qwen2.5
BGE-M3
Redis
LibreOffice
```

### Ollama

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

### Redis

Redis digunakan sebagai distributed lock untuk mencegah proses `sync` dan `ingest` berjalan bersamaan (duplicate/race condition), termasuk saat aplikasi berjalan dengan lebih dari satu worker/process.

#### Development (Windows):

Redis tidak memiliki build resmi untuk Windows, sehingga dijalankan melalui WSL (Windows Subsystem for Linux).

```bash
# di dalam WSL
sudo apt update
sudo apt install -y redis-server
sudo service redis-server start
```

Verifikasi Redis berjalan (masih di dalam WSL):

```bash
redis-cli ping
# PONG
```

Karena Flask app berjalan di Windows sedangkan Redis berjalan di WSL, gunakan `REDIS_URL` yang mengarah ke `localhost` (WSL2 mem-forward port ke Windows secara otomatis):

```env
REDIS_URL=redis://localhost:6379/0
```

#### Production (Ubuntu):

```bash
sudo apt update
sudo apt install -y redis-server
sudo systemctl enable --now redis-server
```

Verifikasi:

```bash
redis-cli ping
# PONG
```

`REDIS_URL` pada production tetap mengarah ke `localhost` selama Redis berjalan pada server yang sama dengan aplikasi:

```env
REDIS_URL=redis://localhost:6379/0
```

### LibreOffice

LibreOffice digunakan untuk konversi `.docx` ke `.pdf` sebelum diproses menjadi markdown (`ingestion/cleaner.py`). Konversi dijalankan headless melalui `subprocess`, bukan library Python.

#### Development (Windows):

Download dan install LibreOffice dari [libreoffice.org](https://www.libreoffice.org/download/download/) menggunakan installer default.

Path executable pada Windows diasumsikan berada pada:

```text
C:\Program Files\LibreOffice\program\soffice.exe
```

Jika LibreOffice diinstall pada path lain, sesuaikan path tersebut pada `ingestion/cleaner.py` (fungsi `_get_libreoffice_command`).

Verifikasi (PowerShell atau CMD):

```powershell
& "C:\Program Files\LibreOffice\program\soffice.exe" --version
```

#### Production (Ubuntu):

```bash
sudo apt update
sudo apt install -y libreoffice
```

Pada Ubuntu, command `libreoffice` diasumsikan sudah tersedia di `PATH` sehingga tidak perlu path executable eksplisit.

Verifikasi:

```bash
libreoffice --version
```

Konversi `.docx` ke `.pdf` menggunakan mode `--headless`, sehingga tidak memerlukan display/GUI dan aman dijalankan pada server tanpa desktop environment.

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
├── sync/
│   ├── export_logs.py
│   ├── retention.py
│   └── sync.py
├── rag/
│   ├── chain.py
│   ├── embeddings.py
│   ├── retriever.py
│   └── vectorstore.py
├── routes/
│   ├── chat.py
│   ├── analytics.py
│   └── admin.py
├── utils/
│   ├── anonymizer.py
│   ├── extensions.py
│   ├── locks.py
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
├── ingest.py
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
Project name: digital-workforce
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
EMBEDDING_MODEL=bge-m3

REDIS_URL=redis://localhost:6379/0
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
cd AI-Digital-Workforce
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

### Tabel

#### `documents`

Menyimpan chunk hasil indexing beserta embedding-nya. Digunakan untuk retrieval (`match_documents`, `hybrid_search`).

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

#### `query_logs`

Mencatat setiap pertanyaan user (setelah anonymization) untuk keperluan analytics seperti Top FAQ. Setiap log terikat pada `anon_id`, bukan identitas user asli.

#### `chat_usage_logs`

Mencatat biaya dan token usage per request chat (embedding + LLM), digunakan untuk laporan cost harian/mingguan dan monitoring budget.

#### `index_usage_logs`

Mencatat biaya dan token usage embedding pada proses indexing dokumen, terpisah dari usage saat chat.

#### `budget_alerts`

Menyimpan histori alert saat penggunaan budget (harian/mingguan) melewati threshold tertentu. Kombinasi `period_type`, `period_date`, dan `alert_type` bersifat unik agar alert yang sama tidak tercatat berulang.

#### `document_status`

Melacak status ingest/sync setiap dokumen (`pending`, `success`, `failed`, dsb) berdasarkan `document_id`, termasuk waktu terakhir diproses (`last_ingested_at`).

### Function

```text
match_documents()
hybrid_search()
get_top_faq()
get_daily_cost_report()
get_weekly_cost_report()
delete_expired_query_logs()
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

Sinkronisasi membandingkan dokumen sumber pada direktori `documents/` dengan data yang terdapat di vector database.

Struktur direktori:

```text
documents/
├── sop/
├── datasheet/
└── pricelist/
```

Format dokumen yang didukung:

```text
.docx
.pdf
.xlsx
```

Status dokumen:

```text
New
Existing
Deleted
```

Contoh output:

```text
[SYNC] datasheet | New: 2 | Existing: 15 | Deleted: 1
```

Dokumen `New` dan `Existing` akan diproses melalui indexing. Fingerprint digunakan untuk melewati chunk yang tidak mengalami perubahan.

Dokumen yang sudah tidak terdapat pada source akan dihapus dari vector database berdasarkan `document_id`.

---

## Admin Endpoints

Sync dan ingest tersedia sebagai endpoint API untuk kebutuhan operasional.

Akses endpoint dibatasi untuk role:

```text
Admin
```

### Ingest Endpoint

Digunakan setelah dokumen sudah tersimpan di sistem, misalnya melalui proses upload terpisah.

```http
POST /api/admin/ingest
Content-Type: application/json
```

Body:

```json
{
  "path": "documents/datasheet/example.pdf"
}
```

Format file yang didukung:

```text
.docx
.pdf
.xlsx
```

Proses indexing dijalankan secara asynchronous menggunakan background thread.

Response:

```json
{
  "message": "ingest started",
  "file": "example.pdf"
}
```

Status code: `202 Accepted`.

Jika ingest untuk file yang sama sedang berjalan, request akan ditolak dengan:

```json
{
  "error": "ingest already running for 'example.pdf'"
}
```

Status code: `409 Conflict`.

### Sync Endpoint

Endpoint ini digunakan untuk melakukan sinkronisasi seluruh dokumen atau hanya satu category.

```http
POST /api/admin/sync
Content-Type: application/json
```

#### Sync seluruh category

Kirim body kosong:

```json
{}
```

Proses akan melakukan sync terhadap:

```text
documents/sop/
documents/datasheet/
documents/pricelist/
```

Response:

```json
{
  "message": "sync started for all categories"
}
```

#### Sync satu category

Contoh:

```json
{
  "category": "datasheet"
}
```

Category yang diperbolehkan:

```text
sop
datasheet
pricelist
```

Response:

```json
{
  "message": "sync started for category 'datasheet'"
}
```

Status code: `202 Accepted`.

Proses sync dijalankan secara asynchronous menggunakan background thread.

Progress dan hasil proses tidak dikembalikan melalui endpoint ini. Gunakan log aplikasi untuk memantau status sinkronisasi.

Jika sync untuk category (atau `all`) yang sama sedang berjalan, request akan ditolak dengan:

```json
{
  "error": "sync already running for 'datasheet'"
}
```

Status code: `409 Conflict`.

Lock disimpan di Redis dengan TTL 3600 detik sebagai safety net apabila proses crash tanpa sempat melepas lock.

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

## Analytics Endpoints

Selain log export, tersedia endpoint analytics tambahan untuk kebutuhan reporting.

Akses dibatasi untuk role:

```text
Marketing
Product
```

### Top FAQ

```http
GET /api/logs/top-faq?days=30&limit=5
```

Mengembalikan daftar pertanyaan yang paling sering diajukan dalam rentang hari tertentu.

| Parameter | Default | Description                          |
| --------- | ------: | ------------------------------------- |
| `days`    |      30 | Rentang hari ke belakang yang dihitung |
| `limit`   |       5 | Jumlah maksimum FAQ yang dikembalikan |

### Cost — Daily

```http
GET /api/cost/daily?date=YYYY-MM-DD
```

Mengembalikan laporan biaya (LLM/embedding) untuk satu hari tertentu. Jika `date` tidak dikirim, menggunakan tanggal berjalan.

### Cost — Weekly

```http
GET /api/cost/weekly?date=YYYY-MM-DD
```

Mengembalikan laporan biaya mingguan hingga tanggal `date` (default: hari ini).

### Cost — Budget

```http
GET /api/cost/budget
```

Mengembalikan status penggunaan budget saat ini terhadap limit yang ditentukan.

Detail lengkap request/response setiap endpoint di atas tersedia pada [`api-contract.md`](docs/api-contract.md).

---

## Deployment

Deployment target: Server Ubuntu dengan Flask dan Ollama berjalan pada server yang sama.

Architecture production:

```text
Frontend
   ↓
HTTPS
   ↓
Nginx (Reverse Proxy)
   ↓
Gunicorn
   ↓
Flask
   ↓
RAG
   ├── Supabase
   ├── BGE-M3 (Ollama)
   └── Qwen2.5 (Ollama)
```

Jangan menggunakan Flask development server (`flask run` / `app.run(debug=True)`) untuk production.

### 1. Setup Server

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip nginx git redis-server libreoffice
sudo systemctl enable --now redis-server
redis-cli ping
libreoffice --version
```

### 2. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5
ollama pull bge-m3
ollama list
```

Ollama berjalan sebagai systemd service pada:

```text
http://127.0.0.1:11434
```

Port ini tidak boleh diekspos langsung ke public internet.

### 3. Deploy Aplikasi

```bash
git clone <repo-url> /opt/AI-Digital-Workforce
cd /opt/AI-Digital-Workforce
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

Buat `.env` sesuai [Konfigurasi Environment](#konfigurasi-environment), lalu batasi permission:

```bash
chmod 600 .env
```

### 4. Jalankan dengan Gunicorn (systemd)

Buat `/etc/systemd/system/AI-Digital-Workforce.service`:

```ini
[Unit]
Description=RAG Chatbot Flask App
After=network.target ollama.service

[Service]
User=www-data
WorkingDirectory=/opt/AI-Digital-Workforce
EnvironmentFile=/opt/AI-Digital-Workforce/.env
ExecStart=/opt/AI-Digital-Workforce/.venv/bin/gunicorn --workers 3 --worker-class gthread --threads 4 --timeout 120 --bind 127.0.0.1:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now AI-Digital-Workforce
sudo systemctl status AI-Digital-Workforce
```

`worker-class gthread` digunakan agar koneksi SSE pada `/api/chat` tidak memblokir worker lain.

### 7. Setup Nginx (Reverse Proxy)

Buat `/etc/nginx/sites-available/AI-Digital-Workforce`:

```nginx
server {
    listen 80;
    server_name saptatunas.com;

    location /api/chat {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/AI-Digital-Workforce /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

`proxy_buffering off` wajib pada `/api/chat` agar SSE stream diteruskan secara real-time, bukan di-buffer oleh Nginx.

### 8. HTTPS dengan Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d saptatunas.com
```

Production harus menggunakan HTTPS.

### 9. Production Environment

Gunakan environment variables untuk:

```text
SUPABASE_URL
SUPABASE_KEY
SUPABASE_SECRET_KEY
OLLAMA_BASE_URL
OLLAMA_LLM
EMBEDDING_MODEL
REDIS_URL
```

Debug mode harus dinonaktifkan:

```text
FLASK_DEBUG=0
```

### 10. Firewall

Batasi akses hanya pada port yang diperlukan:

```bash
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

Port `8000` (Gunicorn) dan `11434` (Ollama) tidak boleh dapat diakses langsung dari luar server.

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