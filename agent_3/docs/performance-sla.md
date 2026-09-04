# Performance SLA – Response Time

## 1. Objective

Menentukan baseline performa dan target SLA response time untuk sistem RAG Chatbot, meliputi proses retrieval, LLM inference, streaming response, dan total end-to-end request.

Pengukuran dilakukan pada environment development yang masih menggunakan laptop dan LLM lokal, sehingga hasil pengukuran saat ini digunakan sebagai **performance baseline**, bukan sebagai representasi final performa production.

## 2. Testing Environment

| Komponen       | Kondisi                               |
| -------------- | ------------------------------------- |
| Environment    | Development / Local                   |
| Hardware       | Laptop                                |
| LLM            | Local LLM inference                   |
| Retrieval      | Embedding + Vector Search + Reranking |
| Response       | Streaming                             |
| Jumlah request | 15                                    |

## 3. Baseline Performance

Berdasarkan 15 request pengujian:

| Metric             | Average |     P95 | Minimum | Maximum |
| ------------------ | ------: | ------: | ------: | ------: |
| Retrieval          | 10.43 s | 10.99 s |  9.56 s | 11.06 s |
| LLM TTFT           | 22.25 s | 24.48 s | 19.36 s | 24.59 s |
| LLM Total          | 46.94 s | 58.92 s | 33.49 s | 61.04 s |
| End-to-End Request | 63.34 s | 78.40 s | 48.17 s | 78.64 s |

### Retrieval Breakdown

Retrieval terdiri dari:

* Embedding generation: ~7.3 s
* Vector / hybrid search: ~0.8 s
* Reranking: ~2.2 s
* Total retrieval: ~10.4 s

Hasil menunjukkan bahwa proses embedding merupakan komponen terbesar dalam latency retrieval.

### LLM Performance

LLM memiliki latency yang lebih tinggi dibandingkan retrieval:

* Average TTFT: ~22.25 s
* P95 TTFT: ~24.48 s
* Average total generation: ~46.94 s
* P95 total generation: ~58.92 s

Latency LLM saat ini dipengaruhi oleh penggunaan **local LLM inference pada laptop**.

## 4. Current Performance Baseline

Current baseline berdasarkan hasil pengujian:

```text
Average End-to-End : ~63.3 seconds
P95 End-to-End     : ~78.4 seconds

Average Retrieval  : ~10.4 seconds
P95 Retrieval      : ~11.0 seconds

Average TTFT       : ~22.3 seconds
P95 TTFT           : ~24.5 seconds
```

Nilai tersebut digunakan sebagai baseline untuk membandingkan performa setelah sistem dipindahkan ke infrastructure production.

## 5. Production SLA Target

SLA production ditetapkan lebih rendah daripada baseline development karena environment production direncanakan menggunakan infrastructure yang lebih sesuai untuk inference dan workload production.

### Target SLA

| Metric                   | Production Target |
| ------------------------ | ----------------: |
| Retrieval P95            |       ≤ 5 seconds |
| LLM TTFT P95             |      ≤ 10 seconds |
| LLM Generation P95       |      ≤ 30 seconds |
| End-to-End Streaming P95 |  **≤ 45 seconds** |

### Primary SLA

> **95% request harus menghasilkan token pertama dalam ≤ 10 detik dan menyelesaikan streaming response dalam ≤ 45 detik.**

SLA ini berlaku setelah sistem berjalan pada production infrastructure.

## 6. Performance Classification

Untuk monitoring internal, response time dikategorikan sebagai berikut:

| End-to-End Response | Status            |
| ------------------: | ----------------- |
|              < 30 s | Good              |
|             30–45 s | Acceptable        |
|             45–60 s | Warning           |
|              > 60 s | Performance Issue |
|     > 45 s pada P95 | SLA Violation     |

Untuk SLA formal, parameter utama adalah **P95**, bukan single request.

## 7. Measurement Method

Response time diukur menggunakan timestamp pada setiap tahap request:

```text
Request
   │
   ├── Logging
   │
   ├── Retrieval
   │     ├── Embedding
   │     ├── Search
   │     └── Reranking
   │
   ├── LLM
   │     ├── TTFT
   │     └── Generation
   │
   └── Streaming completed
```

Metric yang wajib dicatat:

```text
retrieval_total
embedding_time
search_time
rerank_time
llm_ttft
llm_total
request_total
```

## 8. SLA Validation

SLA production belum dinyatakan tercapai berdasarkan pengujian saat ini.

Pengujian saat ini hanya membuktikan:

```text
Development Baseline
P95 E2E = 78.40 s
```

Setelah deployment ke production, dilakukan pengujian ulang menggunakan workload yang representatif.

SLA dinyatakan **PASS** apabila:

```text
P95 Retrieval   ≤ 5 s
P95 TTFT        ≤ 10 s
P95 E2E         ≤ 45 s
```

Jika salah satu parameter melebihi target, dilakukan performance optimization dan pengujian ulang.

## 9. Final SLA

### Development Baseline

```text
P95 Retrieval : ~11 s
P95 TTFT      : ~24.5 s
P95 E2E       : ~78.4 s
```

### Production Target

```text
P95 Retrieval : ≤ 5 s
P95 TTFT      : ≤ 10 s
P95 E2E       : ≤ 45 s
```

**Production SLA:**

> **P95 End-to-End Streaming Response Time ≤ 45 seconds, dengan P95 Time-to-First-Token ≤ 10 seconds.**

Baseline saat ini tidak digunakan sebagai production SLA karena pengujian masih dilakukan pada laptop dengan local LLM inference.
