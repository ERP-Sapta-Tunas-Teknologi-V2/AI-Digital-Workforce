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
  "question": "...",
  "session_id": "uuid (opsional)",
  "user_id": "string (opsional)"
}
```

### Request Parameters

| Parameter    | Type   | Required | Description                                                   |
| ------------ | ------ | -------- | ------------------------------------------------------------- |
| `question`   | string | Ya       | Pertanyaan pengguna (maks. 1000 karakter)                     |
| `session_id` | string | Tidak    | ID session. Jika kosong/tidak ditemukan, session baru dibuat  |
| `user_id`    | string | Tidak    | Identifier user, disimpan pada session (belum diverifikasi)   |

Header opsional: `X-User-Role` (lihat [`rbac-policy.md`](../kebijakan/rbac-policy.md)).
Rate limit: 10 request/menit/IP → `429`.

### Validation

| Condition                   | Response |
| --------------------------- | -------- |
| `question` tidak dikirim    | `400`    |
| `question` bukan string     | `400`    |
| `question` kosong           | `400`    |
| `question` > 1000 karakter  | `400`    |
| terdeteksi prompt injection | `400`    |
| body bukan JSON valid       | `400` (`invalid JSON`) |
| body bukan object           | `400` (`request body must be an object`) |

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

Dikirim sebelum token jawaban. `sources` **tidak lagi** dikirim pada event ini.

```text
data: {"type":"metadata","session_id":"...","request_id":"...","fallback":false}
```

`request_id` dipakai untuk `POST /api/feedback`. `session_id` disimpan client untuk request berikutnya.

### 2. Token Event

Berisi potongan jawaban dari LLM.

```text
data: {"type":"token","content":"..."}
```

Format:

```json
{
  "type": "token",
  "content": "..."
}
```

Frontend menggabungkan `content` dari event `token` untuk menampilkan jawaban secara bertahap.

### 3. Answer Event

Jawaban lengkap setelah streaming selesai. Frontend mengganti buffer token dengan isi ini.

```text
data: {"type":"answer","content":"..."}
```

### 4. Sources Event

Hanya berisi source yang benar-benar disitasi pada jawaban (`[1]`, `[2]`, ...). Jika LLM tidak menyitasi apa pun, `sources` kosong.

```text
data: {"type":"sources","sources":[{"citation":"1","page":[1,2],"source":"...","category":"...","uploaded_at":"...","section_title":"...","version":1}]}
```

### 5. Error Event

Dikirim jika LLM gagal di tengah stream. Stream berhenti tanpa event `done`.

```text
data: {"type":"error","content":"Request gagal diproses."}
```

### 6. Done Event

Menandakan streaming telah selesai.

```text
data: {"type":"done"}
```

## Successful Response Flow

```text
metadata → token… → answer → sources → done
```

Contoh lengkap:

```text
data: {"type":"metadata","session_id":"...","request_id":"...","fallback":false}

data: {"type":"token","content":"..."}

data: {"type":"token","content":"..."}

data: {"type":"answer","content":"..."}

data: {"type":"sources","sources":[...]}

data: {"type":"done"}
```

## Fallback Response (JSON)

Jika hybrid search tidak mengembalikan kandidat sama sekali, backend tidak melakukan proses generation LLM dan mengembalikan JSON biasa (bukan SSE).

> Threshold rerank (`RERANK_THRESHOLD`) saat ini **dinonaktifkan** (dikomentari di `retriever.py`). Jika ada kandidat, 3 teratas selalu dikirim ke LLM, sehingga "Informasi tidak ditemukan" juga bisa muncul sebagai jawaban SSE biasa dengan status log `completed`.

Response:

```json
{
  "session_id": "...",
  "request_id": "...",
  "question": "...",
  "answer": "Informasi tidak ditemukan dalam knowledge base. Silakan hubungi kontak kami.",
  "context": "",
  "sources": [],
  "fallback": true
}
```

`question` berisi query yang sudah di-anonymize. `context` selalu string kosong pada fallback.

`fallback: true` menunjukkan bahwa tidak ditemukan informasi yang relevan dalam knowledge base.

Untuk response normal (SSE), field `fallback` dikirim di dalam metadata event dengan nilai:

```text
fallback: false
```

## Sources

Source dikirim melalui event `sources` (bukan `metadata`) dan hanya berisi chunk yang disitasi pada jawaban.

Contoh:

```json
{
  "type": "sources",
  "sources": [
    {
      "citation": "1",
      "page": [1,2],
      "source": "...",
      "category": "datasheet",
      "uploaded_at": "...",
      "section_title": "...",
      "version": 1
    }
  ]
}
```

Frontend dapat menggunakan `source` untuk menampilkan nama dokumen sumber, dan `citation` untuk mencocokkan nomor sitasi pada teks jawaban.

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

`context` tidak dikirim pada response SSE. Context merupakan data internal RAG yang digunakan oleh backend untuk memberikan informasi kepada LLM. Saat ini field `context` ikut dikirim (kosong) pada fallback JSON.

Frontend menerima:

- `session_id` dan `request_id` melalui metadata event (SSE) atau field fallback JSON
- `token.content` untuk menampilkan jawaban bertahap, dan `answer.content` sebagai jawaban final (SSE)
- `sources` melalui sources event (SSE) atau field `sources` (fallback)
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
  "question": "...",
  "session_id": "..."
}
```

Response menggunakan SSE (normal) atau JSON (fallback):

```text
metadata
→ token…
→ answer
→ sources
→ done
```

FE tidak perlu mengetahui:

- Supabase
- pgvector
- embedding model
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
      sessionId = data.session_id;
      requestId = data.request_id;
    }

    if (data.type === "sources") {
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
Query Validation (+ injection check)
     ↓
Session get/create → History → Contextualizer
     ↓
Interaction log (status: started)
     ↓
Hybrid Search (BGE-M3 + FTS, RRF)
     ↓
Reranking (top 3)
     ↓
Tidak ada dokumen? ── Ya ──→ Fallback JSON
     │ Tidak
     ↓
Qwen2.5 (streaming)
     ↓
SSE: metadata → token… → answer → sources → done
```

> Threshold filtering saat ini nonaktif (`RERANK_THRESHOLD` dikomentari di `retriever.py`). Fallback hanya terjadi jika hybrid search tidak mengembalikan kandidat sama sekali.

## Retrieval Configuration

Parameter retrieval merupakan konfigurasi internal backend dan tidak perlu dikirim oleh frontend.

| Parameter           | Value |
| ------------------- | ----: |
| Candidate documents |    30 |
| Reranked documents  |     3 |
| RRF k               |    10 |
| Reranker            | CrossEncoder (`RERANKER_MODEL`, default Qwen3-Reranker-0.6B) |

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
| Metadata event        | `metadata`           |
| Final answer event    | `answer`             |
| Source event          | `sources`            |
| Error event           | `error`              |
| Completion event      | `done`               |
| Fallback field        | `fallback`           |
| Max query length      | 1000 characters      |

## Daftar Seluruh Endpoint

| Endpoint                                  | Method      | Akses            | Rate limit |
| ----------------------------------------- | ----------- | ---------------- | ---------- |
| `/api/chat`                               | POST        | Public           | 10/menit   |
| `/api/feedback`                           | POST        | Public           | 20/menit   |
| `/api/sources/download`                   | GET         | Public           | 30/menit   |
| `/api/sessions`                           | POST        | Public           | -          |
| `/api/sessions/all`                       | GET         | Public           | -          |
| `/api/sessions/search`                    | POST        | Public           | -          |
| `/api/sessions/<id>`                      | GET, DELETE | Public           | -          |
| `/api/admin/documents/upload`             | POST        | Admin*           | -          |
| `/api/admin/documents`                    | GET         | Admin*           | -          |
| `/api/admin/documents/download`           | GET         | Admin*           | -          |
| `/api/admin/documents/delete`             | DELETE      | Admin*           | -          |
| `/api/admin/ingest`                       | POST        | Admin*           | -          |
| `/api/admin/un-ingest`                    | POST        | Admin*           | -          |
| `/api/admin/sync`                         | POST        | Admin*           | -          |
| `/api/logs/export`                        | GET         | Admin*           | -          |
| `/api/logs/top-faq`                       | GET         | Admin*           | -          |
| `/api/analytics/problematic-answers`      | GET         | Admin*           | -          |
| `/api/analytics/flagged-documents`        | GET         | Admin*           | -          |
| `/api/analytics/dashboard-summary`        | GET         | Admin*           | -          |
| `/`, `/dashboard`                         | GET         | Public (halaman) | -          |

\* `@require_role("Admin")` saat ini dikomentari di `admin.py` dan `analytics.py` (lihat [`rbac-policy.md`](../kebijakan/rbac-policy.md)).

## POST /api/admin/ingest

Endpoint untuk melakukan indexing dokumen yang sudah tersimpan di MinIO.

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
  "category": "datasheet",
  "filename": "example.pdf"
}
```

| Parameter  | Type   | Required | Description                      |
| ---------- | ------ | -------- | --------------------------------- |
| `category` | string | Ya       | Salah satu dari 12 kategori       |
| `filename` | string | Ya       | Nama file yang sudah ada di MinIO |

Format file yang didukung:

```text
.pdf
.docx
.xlsx
.pptx
```

### Response

Proses berjalan secara asynchronous (background thread).

`202 Accepted`:

```json
{
  "message": "ingest started",
  "file": "example.pdf"
}
```

### Error Response

`400 Bad Request`:

```json
{ "error": "category must be one of [...]" }
```

```json
{ "error": "filename is required" }
```

```json
{ "error": "unsupported file type: .jpg" }
```

`404 Not Found` — file tidak ditemukan di MinIO:

```json
{ "error": "file not found in storage" }
```

`409 Conflict` — ingest untuk file yang sama sedang berjalan, **atau** dokumen di-flag `duplicate`/`confidential` (ingest diblokir menunggu review, lihat [`screening.md`](../kebijakan/screening.md)).

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

Body (opsional, boleh kosong `{}` untuk semua kategori):

```json
{
  "category": "datasheet"
}
```

| Parameter  | Type   | Required | Description |
| ---------- | ------ | -------- | ----------- |
| `category` | string | Tidak    | Salah satu dari: general, sop, pricelist, case, meeting, training, solution, proposal, guide, competitive, datasheet, sow. Kosong = semua kategori |

### Response

Proses berjalan secara asynchronous (background thread). Endpoint langsung mengembalikan response tanpa menunggu proses selesai.

`202 Accepted`:

```json
{
  "message": "sync started for category 'datasheet'"
}
```

### Error Response

`400 Bad Request` — category tidak valid:

```json
{
  "error": "category must be one of ['case', 'competitive', ...]"
}
```

`409 Conflict` — sync untuk kategori (atau `all`) yang sama sedang berjalan:

```json
{
  "error": "sync already running for 'datasheet'"
}
```

> Respons `401`/`403` untuk endpoint admin tidak berlaku sampai decorator `require_role` diaktifkan kembali.

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
    "query": "...",
    "total_queries": 12,
    "last_asked": "2026-09-08T09:30:00+07:00"
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

Endpoint pendukung fitur riwayat percakapan pada sidebar widget chat. Frontend chat saat ini memakai `GET /api/sessions/all` (mode localStorage dikomentari di `chat.js`); endpoint ini tidak melakukan validasi ownership (lihat [`session.md`](../kebijakan/session.md#75-sidebar-riwayat-percakapan)).

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
  "user_id": "..."
}
```

| Parameter | Type   | Required | Description                                    |
| --------- | ------ | -------- | ----------------------------------------------- |
| `user_id` | string | Ya       | Mengembalikan session milik `user_id` tersebut |

> Frontend chat saat ini memakai `GET /api/sessions/all`, bukan endpoint ini.

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

---

### GET /api/sessions/all

Mengambil seluruh session terbaru tanpa bergantung pada localStorage client.

#### Response

`200 OK`

```json
[
  { "session_id": "...", "title": "...", "created_at": "...", "last_activity_at": "..." }
]
```

> ⚠️ Endpoint ini mengembalikan **seluruh** session tanpa filter `user_id` atau ownership — konsisten dengan batasan pada [`session.md`](../kebijakan/session.md#10-security--privacy) bahwa session tidak divalidasi kepemilikannya.

---

### POST /api/sessions/search

Mencari session berdasarkan isi pesan (case-insensitive, `ILIKE`).

#### Request

```json
{ "query": "..." }
```

| Parameter | Type   | Required | Description                          |
| --------- | ------ | -------- | ------------------------------------- |
| `query`   | string | Yes      | Teks pencarian, maksimal 200 karakter |

#### Response

`200 OK`

```json
[
  {
    "session_id": "...",
    "title": "...",
    "snippet": "...",
    "matched_role": "user",
    "last_activity_at": "..."
  }
]
```

#### Error Response

`400 Bad Request`:

```json
{ "error": "query is required" }
```
```json
{ "error": "query must not exceed 200 characters" }
```

### GET /api/sessions/{session_id}

Mengambil riwayat pesan satu session (hanya **10 pesan terakhir**), digunakan untuk menampilkan ulang percakapan saat item sidebar diklik.

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

Endpoint untuk mendapatkan daftar dokumen (dikelompokkan per `source` dan `chunk_index`) yang paling sering dirujuk pada jawaban yang mendapat downvote, digunakan untuk mengidentifikasi dokumen yang berpotensi perlu direvisi.

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
    "source": "pricelist_dell.xlsx",
    "chunk_index": 3,
    "flagged_count": 4,
    "total_referenced_count": 10,
    "flag_ratio": 0.40
  }
]
```

`flag_ratio` dihitung dari jumlah downvote dibagi total kemunculan dokumen tersebut pada jawaban yang memiliki feedback (bukan seluruh jawaban).

Jika tidak ada data, mengembalikan array kosong `[]`.

---

## GET /api/analytics/dashboard-summary

Endpoint ringkasan untuk dashboard monitoring. Akses dibatasi untuk role `Admin`.

```http
GET /api/analytics/dashboard-summary?days=30
```

`200 OK`

```json
{
  "query_volume": [{ "date": "2026-09-08", "total": 14 }],
  "total_queries": 120,
  "total_feedback": 30,
  "positive_feedback_rate": 76.67,
  "top_referenced_documents": [{ "source": "...", "category": "...", "referenced_count": 9 }]
}
```

---

## GET /api/sources/download

Mengunduh dokumen sumber dari MinIO (`Content-Disposition: attachment`). Public, 30 request/menit/IP.

```http
GET /api/sources/download?category=datasheet&filename=example.pdf
```

`400` filename kosong · `404` file tidak ditemukan · `500` gagal mengunduh

> ⚠️ Endpoint ini tidak melewati RBAC kategori.

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
embedding_tokens
search
rerank
relevant
total
```

Log waktu dan LLM:

```text
log/log_time.txt             → latency retrieval (embedding, search, rerank, relevant, total) dan LLM (ttft, total, request total)
```

Log dokumen dan rerank score:

```text
log/log_retrieval-docs.txt
```

Log ini digunakan untuk QA dan monitoring latency retrieval.

## QA Retrieval

Performance retrieval dapat dievaluasi menggunakan log:

```text
log/log_time.txt
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