# Knowledge Expert (Agent 3)

Retrieval-Augmented Generation (RAG) untuk melakukan pencarian dokumen dan menghasilkan jawaban berdasarkan knowledge base yang telah di-index.

## Daftar Isi

* [Stack](#stack)
* [Arsitektur](#arsitektur)
* [Requirements](#requirements)
* [Struktur Project](#struktur-project)
* [Setup Supabase](#setup-supabase)
* [Konfigurasi Environment](#konfigurasi-environment)
* [Instalasi](#instalasi)
* [Inisialisasi Database](#inisialisasi-database)
* [Menjalankan Aplikasi](#menjalankan-aplikasi)
* [Deployment](#deployment)
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
* Distributed lock: Redis
* Object storage: MinIO

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

Pipeline document management:

```text
User
   ↓
Dashboard
   ↓
Upload
   ↓
MinIO
   ↓
Select Category
   ↓
{category}/{filename}
   ↓
Ingest
   ↓
Preprocessing
   ↓
Chunking
   ↓
Embedding
   ↓
Supabase / pgvector
```

Diagram alur end-to-end lengkap (document management + runtime) tersedia pada [`project-flow.md`](documentation/referensi-teknis/project-flow.md).

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
MinIO
```

### Ollama

Instal Ollama mengikuti dokumentasi resmi [Ollama Quickstart](https://docs.ollama.com/quickstart).

Model yang digunakan:

```text
qwen2.5
bge-m3
minicpm-v4.5:8b
```

Instal model:

```bash
ollama pull qwen2.5
ollama pull bge-m3
ollama pull minicpm-v4.5:8b
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

### MinIO

MinIO digunakan sebagai object storage untuk menyimpan file dokumen mentah sebelum di-ingest ke Supabase. File disimpan dalam struktur `{bucket}/{category}/{filename}`.

#### Development (Windows via WSL + Docker Desktop)

MinIO dijalankan melalui Docker. Pastikan Docker Desktop terinstal dengan WSL 2 Integration aktif untuk distro yang digunakan (lihat Settings → Resources → WSL Integration).

Jalankan container dari dalam WSL:

```bash
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  --name minio \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=password" \
  -v minio-data:/data \
  minio/minio server /data --console-address ":9001"
```

Jika container `minio` sudah pernah dibuat tetapi sedang berhenti, jalankan kembali dengan:

```bash
docker start minio
```

Port `9000` digunakan untuk API, port `9001` untuk Console (dashboard web).

Akses Console:

```text
http://localhost:9001
```

Login menggunakan `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` yang telah ditentukan.

Bucket akan dibuat otomatis oleh aplikasi saat startup (`ensure_bucket()`), tidak perlu dibuat manual.

#### Production (Ubuntu)

Instalasi dan konfigurasi mengikuti pola yang sama menggunakan Docker, dengan `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` yang kuat dan tidak menggunakan nilai default. Port `9000`/`9001` tidak diekspos langsung ke public internet — akses ke Console dibatasi melalui VPN/SSH tunnel atau reverse proxy dengan autentikasi tambahan.

#### MinIO Client (`mc`)

`mc` adalah CLI resmi untuk mengelola MinIO secara langsung (list, hapus, kosongkan bucket, dsb), terpisah dari operasi yang dilakukan lewat aplikasi.

Instalasi (Linux/WSL):

```bash
curl -L https://dl.min.io/client/mc/release/linux-amd64/mc -o mc
chmod +x mc
sudo mv mc /usr/local/bin/
mc --version
```

Tambahkan alias koneksi:

```bash
mc alias set myminio http://localhost:9000 admin password
```

Contoh penggunaan:

```bash
mc ls myminio                        # list bucket
mc rm --recursive --force myminio/knowledge-expert   # kosongkan isi bucket
mc rb --force myminio/knowledge-expert      # hapus bucket beserta isinya
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
├── session/
│   ├── manager.py
│   ├── memory.py
│   └── contextualizer.py
├── utils/
│   ├── anonymizer.py
│   ├── extensions.py
│   ├── locks.py
│   ├── minio_client.py
│   ├── permissions.py
│   ├── query_logger.py
│   ├── status_tracker.py
│   ├── supabase_admin.py
│   └── supabase_client.py
├── static/
│   ├── chat.html
│   ├── chat.js
│   ├── chat.css
│   ├── dashboard.html
│   ├── dashboard.js
│   └── dashboard.css
├── tests/
├── log/
├── documentation/
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

Daftar lengkap tabel dan function tersedia pada [`database-schema.md`](documentation/referensi-teknis/database-schema.md).

---

## Menjalankan Aplikasi

### Development (Windows)

Pastikan seluruh service dependency berjalan sebelum menjalankan Flask app.

#### 1. WSL — jalankan MinIO dan Redis:

```bash
docker start minio
sudo service redis-server start
```

#### 2. Aktifkan Ollama

Pastikan Ollama sudah berjalan (buka aplikasi Ollama atau jalankan `ollama serve` jika belum berjalan sebagai service).

#### 3. VS Code Terminal — jalankan Flask app:

```bash
cd knowledge-expert
```

```bash
flask run
```

Atau dengan mode debug (auto-reload saat ada perubahan kode):

```bash
flask run --debug
```

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
ollama pull minicpm-v4.5:8b
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

### 5. Setup Nginx (Reverse Proxy)

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

### 6. HTTPS dengan Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d saptatunas.com
```

Production harus menggunakan HTTPS.

### 7. Production Environment

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

### 8. Firewall

Batasi akses hanya pada port yang diperlukan:

```bash
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

Port `8000` (Gunicorn) dan `11434` (Ollama) tidak boleh dapat diakses langsung dari luar server.

---

## Dokumentasi

Dokumentasi detail tersedia di directory [`documentation/`](documentation):

### API & Operasional

* [`api-contract.md`](documentation/api-operasional/api-contract.md) — API contract dan frontend integration
* [`admin-endpoints.md`](documentation/api-operasional/admin-endpoints.md) — endpoint upload, ingest, un-ingest, delete, sync
* [`dashboard.md`](documentation/api-operasional/dashboard.md) — panduan Dashboard Dokumen
* [`indexing-and-sync.md`](documentation/api-operasional/indexing-and-sync.md) — indexing manual dan sinkronisasi dokumen
* [`analytics-endpoints.md`](documentation/api-operasional/analytics-endpoints.md) — top FAQ, problematic answers, flagged documents

### Kebijakan

* [`session.md`](documentation/kebijakan/session.md) — session dan conversation management
* [`cors-policy.md`](documentation/kebijakan/cors-policy.md) — CORS policy
* [`rate-limit-policy.md`](documentation/kebijakan/rate-limit-policy.md) — rate limiting
* [`rbac-policy.md`](documentation/kebijakan/rbac-policy.md) — role-based access control
* [`retention-policy.md`](documentation/kebijakan/retention-policy.md) — data retention dan cleanup
* [`security-nfr.md`](documentation/kebijakan/security-nfr.md) — encryption at rest & TLS in transit
* [`screening.md`](documentation/kebijakan/screening.md) — pemeriksaan dokumen (duplikat, rahasia, usang)
* [`versioning.md`](documentation/kebijakan/versioning.md) — versioning dokumen kategori Pricelist

### Referensi Teknis

* [`database-schema.md`](documentation/referensi-teknis/database-schema.md) — tabel dan function Supabase
* [`performance-sla.md`](documentation/referensi-teknis/performance-sla.md) — performance baseline dan production SLA
* [`logging.md`](documentation/referensi-teknis/logging.md) — query logging, anonymization, feedback
* [`project-flow.md`](documentation/referensi-teknis/project-flow.md) — diagram alur end-to-end
* [`testing.md`](documentation/referensi-teknis/testing.md) — menjalankan test