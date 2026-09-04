# API Contract

## POST /api/chat

Endpoint untuk mengirim pertanyaan pengguna dan mendapatkan jawaban RAG secara streaming.

### Request

```http
POST /api/chat
Content-Type: application/json
```

Body:

```json
{
  "question": "..."
}
```

### Request Parameters

| Parameter  | Type   | Required | Description         |
| ---------- | ------ | -------- | ------------------- |
| `question` | string | Yes      | Pertanyaan pengguna |

### Validation

| Condition                   | Response |
| --------------------------- | -------- |
| `question` tidak dikirim    | `400`    |
| `question` bukan string     | `400`    |
| `question` kosong           | `400`    |
| `question` > 1000 karakter  | `400`    |
| terdeteksi prompt injection | `400`    |

Contoh:

```json
{
  "error": "question is required"
}
```

## Response Type

Endpoint memiliki dua kemungkinan response:

1. **Relevant chunks ditemukan**
   - HTTP `200`
   - Content-Type: `text/event-stream`
   - Response berupa SSE

2. **Tidak ada relevant chunks**
   - HTTP `200`
   - Content-Type: `application/json`
   - Response berupa fallback JSON

## Response (SSE)

Endpoint menggunakan Server-Sent Events (SSE) untuk response normal.

Content-Type:

```text
text/event-stream
```

Response terdiri dari beberapa event.

### 1. Metadata Event

Dikirim sebelum token jawaban.

```text
data: {"type":"metadata","sources":[...],"fallback":false}
```

Format:

```json
{
  "type": "metadata",
  "sources": [
    {
      "source": "...",
      "section_title": "...",
      "uploaded_at": "..."
    }
  ],
  "fallback": false
}
```

### 2. Token Event

Berisi potongan jawaban dari LLM.

```text
data: {"type":"token","content":"..."}
data: {"type":"token","content":"..."}
data: {"type":"token","content":"..."}
```

Format:

```json
{
  "type": "token",
  "content": "..."
}
```

Frontend harus menggabungkan seluruh `content` dari event `token` untuk membentuk jawaban lengkap.

### 3. Done Event

Menandakan streaming telah selesai.

```text
data: {"type":"done"}
```

Format:

```json
{
  "type": "done"
}
```

## Successful Response Flow

```text
POST /api/chat
        ↓
metadata
        ↓
token
        ↓
token
        ↓
token
        ↓
...
        ↓
done
```

Contoh lengkap:

```text
data: {"type":"metadata","sources":[{"source":"...","section_title":"...","uploaded_at":"..."}],"fallback":false}

data: {"type":"token","content":"..."}

data: {"type":"token","content":"..."}

data: {"type":"token","content":"..."}

data: {"type":"done"}
```

## Fallback Response (JSON)

Jika tidak ada chunk yang memenuhi threshold retrieval, backend tidak melakukan proses generation LLM dan mengembalikan JSON biasa (bukan SSE).

Response:

```json
{
  "question": "...",
  "answer": "Informasi tidak ditemukan dalam knowledge base. Silakan hubungi kontak kami.",
  "sources": [],
  "fallback": true
}
```

`fallback: true` menunjukkan bahwa tidak ditemukan informasi yang relevan dalam knowledge base.

Untuk response normal (SSE), field `fallback` dikirim di dalam metadata event dengan nilai:

```text
fallback: false
```

## Sources

`metadata.sources` (pada SSE) berisi source dari chunk yang benar-benar digunakan untuk menghasilkan jawaban.

Contoh:

```json
{
  "sources": [
    {
      "source": "...",
      "section_title": "...",
      "uploaded_at": "..."
    }
  ]
}
```

Frontend dapat menggunakan `source` untuk menampilkan nama dokumen sumber.

Field internal berikut tidak perlu digunakan oleh frontend:

```text
retrieval_score
rerank_score
document_id
chunk_index
fingerprint
content
embedding
```

## Context

`context` tidak dikirim ke frontend.

Context merupakan data internal RAG yang digunakan oleh backend untuk memberikan informasi kepada LLM.

Frontend menerima:

- `question` pada fallback response
- `token.content` untuk membentuk answer (response normal/SSE)
- `sources` melalui metadata event (response normal/SSE) atau field `sources` (fallback)
- `fallback` untuk mengetahui apakah response merupakan fallback

## Error Response

### 400 Bad Request

Contoh:

```json
{
  "error": "question is required"
}
```

atau:

```json
{
  "error": "question must not exceed 1000 characters"
}
```

atau:

```json
{
  "error": "invalid question"
}
```

### 500 Internal Server Error

Jika terjadi error pada backend:

```json
{
  "error": "Internal server error"
}
```

## Frontend Integration

FE widget hanya perlu berkomunikasi dengan satu endpoint:

```text
POST /api/chat
```

Request:

```json
{
  "question": "..."
}
```

Response menggunakan SSE (normal) atau JSON (fallback):

```text
metadata
→ token
→ token
→ token
→ ...
→ done
```

FE tidak perlu mengetahui:

- Supabase
- pgvector
- embedding model
- Voyage AI
- hybrid search
- reranker
- RRF
- chunking
- fingerprint
- context

Dengan demikian implementasi RAG di backend dapat berubah tanpa mengubah kontrak API FE.

Frontend menggunakan `fetch()` karena request `/api/chat` menggunakan method `POST` dan response (normal) berupa streaming.

Contoh (dengan buffer, aman terhadap SSE event yang terpotong di tengah network chunk):

```js
const response = await fetch("/api/chat", {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    question: userQuestion
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

let buffer = "";
let answer = "";

while (true) {
  const {value, done} = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, {stream: true});

  const events = buffer.split("\n\n");
  buffer = events.pop();

  for (const event of events) {
    if (!event.startsWith("data: ")) continue;

    const data = JSON.parse(event.slice(6));

    if (data.type === "metadata") {
      console.log("Sources:", data.sources);
    }

    if (data.type === "token") {
      answer += data.content;
      console.log(answer);
    }

    if (data.type === "done") {
      console.log("Streaming selesai");
    }
  }
}
```

## Backend Internal Flow

```text
User Question
     ↓
Query Validation
     ↓
Hybrid Search
     ↓
Candidate Documents
     ↓
Reranking
     ↓
Threshold Filtering
     ↓
No Relevant Chunk?
     ├── Yes → Fallback Response
     │
     └── No
          ↓
       Sources
          ↓
       Dola Seed
          ↓
       Streaming
          ↓
       SSE
          ↓
       FE Widget
```

## Retrieval Configuration

Parameter retrieval merupakan konfigurasi internal backend dan tidak perlu dikirim oleh frontend.

| Parameter           | Value |
| ------------------- | ----: |
| Candidate documents |    10 |
| Reranked documents  |     3 |
| RRF k               |    50 |

## API Contract Summary

| Item                  | Value                |
| ---------------------- | -------------------- |
| Endpoint              | `/api/chat`          |
| Method                | `POST`               |
| Request               | JSON                 |
| Normal response       | SSE                  |
| Fallback response     | JSON                 |
| Normal Content-Type   | `text/event-stream`  |
| Fallback Content-Type | `application/json`   |
| Query field           | `question`           |
| Streaming event       | `token`              |
| Source event          | `metadata`           |
| Completion event      | `done`               |
| Fallback field        | `fallback`           |
| Max query length      | 1000 characters      |

## Daftar Seluruh Endpoint

| Endpoint               | Method | Akses           |
| ----------------------- | ------ | --------------- |
| `/api/chat`             | POST   | Public          |
| `/api/admin/ingest`     | POST   | Admin           |
| `/api/admin/sync`       | POST   | Admin           |
| `/api/logs/export`      | GET    | Marketing, Product |
| `/api/logs/top-faq`     | GET    | Marketing, Product |
| `/api/cost/daily`       | GET    | Marketing, Product |
| `/api/cost/weekly`      | GET    | Marketing, Product |
| `/api/cost/budget`      | GET    | Marketing, Product |
| `/`                     | GET    | Public          |

## POST /api/admin/ingest

Endpoint untuk melakukan indexing dokumen yang sudah tersimpan di sistem.

### Akses

Dibatasi untuk role:

```text
Admin
```

### Request

```http
POST /api/admin/ingest
Content-Type: application/json
```

Body:

```json
{
  "path": "path/to/file.docx"
}
```

| Parameter | Type   | Required | Description                         |
| --------- | ------ | -------- | ------------------------------------ |
| `path`    | string | Yes      | Path file dokumen yang akan di-index |

Format file yang didukung:

```text
.docx
.pdf
```

### Response

Proses berjalan secara asynchronous (background thread).

`202 Accepted`:

```json
{
  "message": "ingest started",
  "file": "file.docx"
}
```

### Error Response

`400 Bad Request` — path tidak dikirim atau ekstensi tidak didukung:

```json
{
  "error": "path is required"
}
```

```json
{
  "error": "unsupported file type: .jpg"
}
```

`404 Not Found` — file tidak ditemukan di path yang diberikan:

```json
{
  "error": "file not found"
}
```

`401` / `403` — sama seperti `/api/admin/sync`.

---

## POST /api/admin/sync

Endpoint untuk menjalankan sinkronisasi dokumen berdasarkan kategori secara manual/on-demand.

### Akses

Dibatasi untuk role:

```text
Admin
```

Role dikirim melalui header:

```http
X-User-Role: Admin
```

### Request

```http
POST /api/admin/sync
Content-Type: application/json
```

Body:

```json
{
  "category": "stt"
}
```

| Parameter  | Type   | Required | Description                                                              |
| ---------- | ------ | -------- | ------------------------------------------------------------------------ |
| `category` | string | Yes      | Nama folder di root project (berisi dokumen sumber); `berita` atau `stt` |

### Response

Proses berjalan secara asynchronous (background thread). Endpoint langsung mengembalikan response tanpa menunggu proses selesai.

`202 Accepted`:

```json
{
  "message": "sync started for category 'berita'"
}
```

### Error Response

`400 Bad Request` — category tidak valid:

```json
{
  "error": "category must be one of ['berita', 'stt']"
}
```

`401 Unauthorized` — role tidak dikirim:

```json
{
  "error": "authentication required"
}
```

`403 Forbidden` — role tidak memiliki akses:

```json
{
  "error": "forbidden"
}
```

---

## GET /api/logs/export

Endpoint untuk mengekspor query log dalam format CSV.

### Akses

Dibatasi untuk role:

```text
Marketing
Product
```

### Request

```http
GET /api/logs/export?start=YYYY-MM-DD&end=YYYY-MM-DD
```

| Parameter | Type   | Required | Description                                   |
| --------- | ------ | -------- | ---------------------------------------------- |
| `start`   | string | No       | Tanggal awal filter (format `YYYY-MM-DD`)      |
| `end`     | string | No       | Tanggal akhir filter (format `YYYY-MM-DD`, inklusif) |

### Response

`200 OK`

```text
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename=query_logs.csv
```

Body berupa data CSV query log (UTF-8 dengan BOM).

### Error Response

`400 Bad Request`:

```json
{
  "error": "date must use YYYY-MM-DD format"
}
```

```json
{
  "error": "start must not be after end"
}
```

---

## GET /api/logs/top-faq

Endpoint untuk mendapatkan pertanyaan yang paling sering diajukan (top FAQ).

### Akses

Dibatasi untuk role:

```text
Marketing
Product
```

### Request

```http
GET /api/logs/top-faq?days=30&limit=5
```

| Parameter | Type    | Required | Default | Description                          |
| --------- | ------- | -------- | ------- | ------------------------------------- |
| `days`    | integer | No       | 30      | Rentang hari ke belakang yang dihitung |
| `limit`   | integer | No       | 5       | Jumlah maksimum FAQ yang dikembalikan |

### Response

`200 OK`

```json
[
  {
    "question": "...",
    "count": 0
  }
]
```

Jika tidak ada data, mengembalikan array kosong `[]`.

---

## GET /api/cost/daily

Endpoint untuk mendapatkan laporan biaya (cost) harian.

### Akses

Dibatasi untuk role:

```text
Marketing
Product
```

### Request

```http
GET /api/cost/daily?date=YYYY-MM-DD
```

| Parameter | Type   | Required | Description                                    |
| --------- | ------ | -------- | ----------------------------------------------- |
| `date`    | string | No       | Tanggal laporan. Default: hari ini (server-side) |

### Response

`200 OK`

```json
{
  "report_date": "...",
  "total_cost": 0
}
```

Jika tidak ada data untuk tanggal tersebut, mengembalikan object kosong `{}`.

---

## GET /api/cost/weekly

Endpoint untuk mendapatkan laporan biaya (cost) mingguan.

### Akses

Dibatasi untuk role:

```text
Marketing
Product
```

### Request

```http
GET /api/cost/weekly?date=YYYY-MM-DD
```

| Parameter | Type   | Required | Description                                                  |
| --------- | ------ | -------- | -------------------------------------------------------------- |
| `date`    | string | No       | Tanggal akhir periode mingguan. Default: hari ini (server-side) |

### Response

`200 OK`

```json
{
  "data": [
    {
      "report_date": "...",
      "total_cost": 0
    }
  ]
}
```

Jika tidak ada data, `data` berupa array kosong `[]`.

---

## GET /api/cost/budget

Endpoint untuk memeriksa status penggunaan budget saat ini.

### Akses

Dibatasi untuk role:

```text
Marketing
Product
```

### Request

```http
GET /api/cost/budget
```

Tidak ada parameter.

### Response

`200 OK`

```json
{
  "...": "..."
}
```

Struktur response bergantung pada implementasi `check_budget()`.

---

## Analytics Endpoints — Error Response (Umum)

Berlaku untuk seluruh endpoint `/api/logs/*` dan `/api/cost/*`:

`401 Unauthorized` — role tidak dikirim:

```json
{
  "error": "authentication required"
}
```

`403 Forbidden` — role tidak memiliki akses:

```json
{
  "error": "forbidden"
}
```

---

## Performance Logging

Retrieval mencatat:

```text
embedding
search
rerank
threshold
relevant
total
```

Log waktu:

```text
log/log_retrieval-time.txt
```

Log dokumen dan rerank score:

```text
log/log_retrieval-docs.txt
```

Log ini digunakan untuk QA dan monitoring latency retrieval.

## QA Retrieval

Performance retrieval dapat dievaluasi menggunakan log:

```text
log/log_retrieval-time.txt
log/log_retrieval-docs.txt
```

Metric utama:

```text
Embedding latency
Semantic/hybrid search latency
Reranking latency
Total retrieval latency
```

Tujuannya untuk mengetahui tahap mana yang menjadi bottleneck sebelum API digunakan pada FE widget production.