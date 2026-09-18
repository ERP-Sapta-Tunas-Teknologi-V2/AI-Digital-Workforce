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
      "page": [1,2],
      "source": "...",
      "category": "datasheet",
      "uploaded_at": "...",
      "section_title": "...",
      "version": 1
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
data: {"type":"metadata","sources":[...],"fallback":false}

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
      "page": [1,2],
      "source": "...",
      "category": "datasheet",
      "uploaded_at": "...",
      "section_title": "...",
      "version": 1
    }
  ],
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
| `/api/feedback`         | POST   | Public          |
| `POST /api/sessions`    | POST   | Public          |
| `GET /api/sessions/<id>`| GET    | Public          |
| `DELETE /api/sessions/<id>` | DELETE | Public      |
| `/api/admin/ingest`     | POST   | Admin           |
| `/api/admin/sync`       | POST   | Admin           |
| `/api/logs/export`      | GET    | Admin           |
| `/api/logs/top-faq`     | GET    | Admin           |
| `/api/analytics/problematic-answers` | GET | Admin |
| `/api/analytics/flagged-documents`   | GET | Admin |
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

Dibatasi untuk role `Admin`.

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
Content-Disposition: attachment; filename=interaction_logs.csv
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

Dibatasi untuk role `Admin`.

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

## POST /api/feedback

Endpoint untuk mengirim feedback (thumbs up/down beserta alasan opsional) terhadap suatu jawaban chatbot.

### Akses

Public — tidak dibatasi role, dapat dipanggil oleh widget chat publik.

### Request

```http
POST /api/feedback
Content-Type: application/json
```

Body:

```json
{
  "request_id": "...",
  "rating": "up",
  "reason": null
}
```

| Parameter    | Type   | Required | Description                                    |
| ------------ | ------ | -------- | ----------------------------------------------- |
| `request_id` | string | Yes      | `request_id` yang diterima pada metadata/fallback response `/api/chat` |
| `rating`     | string | Yes      | `up` atau `down`                                 |
| `reason`     | string | No       | Alasan feedback, khususnya untuk `down`          |

Satu `request_id` hanya dapat memiliki satu feedback. Mengirim feedback baru untuk `request_id` yang sama akan menimpa (upsert) feedback sebelumnya, bukan menambah entri baru.

### Response

`201 Created`:

```json
{
  "message": "feedback recorded"
}
```

### Error Response

`400 Bad Request`:

```json
{ "error": "request_id is required" }
```

```json
{ "error": "rating must be 'up' or 'down'" }
```

`404 Not Found` — `request_id` tidak ditemukan pada `interaction_logs` (misalnya sudah melewati retention period):

```json
{ "error": "request_id not found" }
```

`500 Internal Server Error`:

```json
{ "error": "failed to record feedback" }
```

### Rate Limit

```text
20 request / menit / IP
```

---

## Sessions (Sidebar)

Endpoint pendukung fitur riwayat percakapan pada sidebar widget chat. Karena widget publik tidak memiliki authentication, daftar `session_id` disimpan di localStorage browser client; endpoint ini tidak melakukan validasi ownership (lihat [`session.md`](../kebijakan/session.md#75-sidebar-riwayat-percakapan)).

### POST /api/sessions

Mengambil metadata sejumlah session sekaligus, digunakan untuk render daftar sidebar.

#### Request

```http
POST /api/sessions
Content-Type: application/json
```

Body:

```json
{
  "session_ids": ["...", "..."]
}
```

| Parameter      | Type  | Required | Description                                   |
| --------------- | ----- | -------- | ------------------------------------------------ |
| `session_ids`  | array | Yes      | Daftar `session_id` yang tersimpan di localStorage client |

#### Response

`200 OK`

```json
[
  {
    "session_id": "...",
    "title": "...",
    "created_at": "...",
    "last_activity_at": "..."
  }
]
```

Session yang sudah dihapus atau tidak ditemukan tidak muncul pada hasil (bukan error). Diurutkan dari `last_activity_at` terbaru.

#### Error Response

`400 Bad Request`:

```json
{ "error": "session_ids must be an array" }
```

---

### GET /api/sessions/{session_id}

Mengambil riwayat pesan lengkap satu session, digunakan untuk menampilkan ulang percakapan saat item sidebar diklik.

#### Request

```http
GET /api/sessions/{session_id}
```

#### Response

`200 OK`

```json
{
  "session_id": "...",
  "title": "...",
  "messages": [
    { "role": "user", "content": "...", "sources": null, "created_at": "..." },
    { "role": "assistant", "content": "...", "sources": [
      {
        "citation": "1",
        "page": [1,2],
        "source": "...",
        "category": "...",
        "uploaded_at": "...",
        "section_title": "...",
        "version": 1
      }
    ], "created_at": "..." }
  ]
}
```

`sources` bernilai `null` untuk pesan `user` atau jawaban fallback.

#### Error Response

`404 Not Found` — session tidak ditemukan atau sudah expired:

```json
{ "error": "session not found or expired" }
```

---

### DELETE /api/sessions/{session_id}

Menghapus session beserta seluruh riwayat pesannya secara permanen (cascade ke `session_messages`).

#### Request

```http
DELETE /api/sessions/{session_id}
```

#### Response

`200 OK`

```json
{ "message": "session deleted" }
```

#### Error Response

`404 Not Found`:

```json
{ "error": "session not found" }
```

`500 Internal Server Error`:

```json
{ "error": "failed to delete session" }
```

---

## GET /api/analytics/problematic-answers

Endpoint untuk mendapatkan daftar jawaban chatbot dengan feedback negatif (downvote) terbanyak.

### Akses

Dibatasi untuk role `Admin`.

### Request

```http
GET /api/analytics/problematic-answers?days=30&min_downvotes=1&limit=20
```

| Parameter       | Type    | Required | Default | Description                                     |
| --------------- | ------- | -------- | ------- | ------------------------------------------------ |
| `days`          | integer | No       | 30      | Rentang hari ke belakang yang dihitung           |
| `min_downvotes` | integer | No       | 1       | Jumlah downvote minimum agar jawaban ditampilkan |
| `limit`         | integer | No       | 20      | Jumlah maksimum hasil yang dikembalikan          |

### Response

`200 OK`

```json
[
  {
    "request_id": "...",
    "question": "...",
    "answer": "...",
    "sources": [...],
    "upvotes": 0,
    "downvotes": 3,
    "reasons": ["jawaban tidak relevan", "harga sudah tidak berlaku"],
    "last_feedback_at": "..."
  }
]
```

Jika tidak ada data, mengembalikan array kosong `[]`.

---

## GET /api/analytics/flagged-documents

Endpoint untuk mendapatkan daftar dokumen yang paling sering dirujuk pada jawaban yang mendapat downvote, digunakan untuk mengidentifikasi dokumen yang berpotensi perlu direvisi.

### Akses

Dibatasi untuk role `Admin`.

### Request

```http
GET /api/analytics/flagged-documents?days=30&limit=20
```

| Parameter | Type    | Required | Default | Description                             |
| --------- | ------- | -------- | ------- | ---------------------------------------- |
| `days`    | integer | No       | 30      | Rentang hari ke belakang yang dihitung   |
| `limit`   | integer | No       | 20      | Jumlah maksimum hasil yang dikembalikan  |

### Response

`200 OK`

```json
[
  {
    "document_id": "pricelist:dell",
    "source": "pricelist_dell.xlsx",
    "category": "pricelist",
    "flagged_count": 4,
    "total_referenced_count": 10,
    "flag_ratio": 0.40
  }
]
```

`flag_ratio` dihitung dari jumlah downvote dibagi total kemunculan dokumen tersebut pada jawaban yang memiliki feedback (bukan seluruh jawaban).

Jika tidak ada data, mengembalikan array kosong `[]`.

---

## Analytics Endpoints — Error Response (Umum)

Berlaku untuk seluruh endpoint `/api/logs/*`:

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