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