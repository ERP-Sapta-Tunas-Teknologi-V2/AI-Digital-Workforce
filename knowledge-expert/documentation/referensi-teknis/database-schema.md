# Database Schema

Skema lengkap tersedia pada [`supabase.sql`](../../supabase.sql). Jalankan file ini melalui `Supabase → SQL Editor` untuk inisialisasi database.

## Daftar Tabel

```text
documents
interaction_logs
response_feedback
document_status
ingestion_logs
document_flags
sessions
session_messages
```

---

## `documents`

Menyimpan chunk hasil indexing beserta embedding-nya. Digunakan untuk retrieval (`match_documents`, `hybrid_search`).

| Column        | Type         | Nullable | Default             | Description                                                                 |
| ------------- | ------------ | -------- | -------------------- | ----------------------------------------------------------------------------- |
| `id`          | bigserial    | No       | auto increment       | Primary key.                                                                  |
| `content`     | text         | Yes      | -                     | Isi teks chunk hasil chunking dokumen.                                        |
| `metadata`    | jsonb        | Yes      | -                     | Metadata chunk: `category`, `section_title`, `source`, `page`, `uploaded_at`, `version`, dll. |
| `document_id` | text         | No       | -                     | Identitas dokumen, format `{category}:{filename_tanpa_ekstensi}`.             |
| `chunk_index` | int          | No       | -                     | Urutan/index chunk dalam satu dokumen.                                        |
| `fingerprint` | text         | No       | -                     | SHA-256 dari isi chunk, dipakai untuk skip re-embedding jika konten tidak berubah. |
| `embedding`   | vector(1024) | Yes      | -                     | Vector embedding dari `content`, dihasilkan oleh model BGE-M3.                |
| `fts`         | tsvector     | Yes      | generated (stored)    | Kolom generated dari `content` (`to_tsvector('simple', content)`), dipakai untuk full-text search. |

**Index & constraint:**

| Nama                                    | Jenis         | Kolom                          | Keterangan                                  |
| ---------------------------------------- | ------------- | -------------------------------- | --------------------------------------------- |
| `documents_document_chunk_unique`        | unique index  | `document_id, chunk_index`      | Mencegah duplikasi chunk pada dokumen sama.   |
| `documents_fts_idx`                      | GIN index     | `fts`                           | Mempercepat full-text search.                 |

**Access control:** RLS aktif, role `anon` diberi akses penuh (`select`, `insert`, `update`, `delete`) melalui policy `Allow insert/select/update/delete documents` — dipakai karena proses ingestion saat ini berjalan dengan Supabase publishable key.

---

## `interaction_logs`

Mencatat setiap pertanyaan user (setelah anonymization), jawaban chatbot, dokumen/chunk yang dirujuk (`sources`), dan status pemrosesan request untuk keperluan analytics seperti Top FAQ, identifikasi jawaban bermasalah, dan identifikasi dokumen yang perlu direvisi.

| Column       | Type         | Nullable | Default           | Description                                                              |
| ------------ | ------------ | -------- | ------------------- | --------------------------------------------------------------------------- |
| `id`         | bigint       | No       | identity            | Primary key.                                                                |
| `request_id` | text         | No      | -                    | ID unik per request `/api/chat`, dipakai untuk korelasi dengan feedback. |
| `session_id` | text         | No      | -                    | ID sesi percakapan (lihat [`session.md`](../kebijakan/session.md)).                     |
| `query`      | text         | No       | -                    | Pertanyaan user, sudah melalui anonymization (PII diganti placeholder).    |
| `answer`     | text         | Yes      | -                    | Jawaban chatbot untuk request tersebut, diisi asynchronous setelah streaming selesai. |
| `sources`    | jsonb        | Yes      | -                    | Array metadata chunk yang dirujuk untuk menghasilkan jawaban.               |
| `status`     | text        | No       | `'started'` | Status pemrosesan request: `started`, `completed`, `fallback`, atau `failed`.          |
| `timestamp`  | timestamptz  | No       | `now()`              | Waktu query diterima.                                                       |
| `anon_id`    | uuid         | No       | -                    | Identifier anonim per request (bukan identitas user asli).                 |

**Status constraint:**

Kolom `status` memiliki constraint `interaction_logs_status_check` yang hanya mengizinkan nilai:

* `started` — request diterima dan sedang diproses.
* `completed` — request berhasil menghasilkan jawaban.
* `fallback` — informasi tidak ditemukan dalam knowledge base sehingga fallback response diberikan.
* `failed` — request gagal diproses.

**Index & constraint:**

| Nama                                     | Jenis         | Kolom         | Keterangan                                   |
| ------------------------------------------ | ------------- | -------------- | ----------------------------------------------- |
| `idx_interaction_logs_timestamp`           | index         | `timestamp`    | Mempercepat query berbasis rentang waktu.       |
| `interaction_logs_request_id_unique`       | unique index  | `request_id`   | Satu `request_id` hanya satu baris.             |
| `interaction_logs_status_check`      | check constraint | `status`     | Membatasi status ke `started`, `completed`, `fallback`, atau `failed`. |


**Access control:** RLS aktif. Role `anon` hanya boleh `insert` (policy `Allow anon insert query logs`). Role `service_role` punya `select`, `insert`, `update` (dipakai untuk mengisi `answer` dan `sources` setelah streaming selesai).

**Retensi:** bertingkat — 30 hari untuk baris tanpa feedback, 90 hari untuk baris dengan feedback (lihat [`retention-policy.md`](../kebijakan/retention-policy.md)), dieksekusi melalui function `delete_expired_interaction_logs()`.

---

## `response_feedback`

Menyimpan feedback pengguna (thumbs up/down beserta alasan opsional) terhadap suatu jawaban chatbot.

| Column       | Type        | Nullable | Default   | Description                                                             |
| ------------ | ----------- | -------- | ---------- | --------------------------------------------------------------------------- |
| `id`         | bigserial   | No       | auto       | Primary key.                                                                |
| `request_id` | text        | No       | -          | Foreign key ke `interaction_logs.request_id`, `on delete cascade`.          |
| `rating`     | text        | No       | -          | `up` atau `down` (`check constraint`).                                     |
| `reason`     | text        | Yes      | -          | Alasan feedback, terutama untuk `down`.                                    |
| `created_at` | timestamptz | Yes      | `now()`    | Waktu feedback dikirim.                                                    |

**Index & constraint:**

| Nama                                        | Jenis         | Kolom         | Keterangan                                        |
| ---------------------------------------------- | ------------- | -------------- | ------------------------------------------------------ |
| `idx_response_feedback_request_id`             | index         | `request_id`   | Mempercepat lookup feedback per request.                |
| `idx_response_feedback_rating`                 | index         | `rating`       | Mempercepat filter/agregasi per rating.                 |
| `response_feedback_request_id_unique`          | unique        | `request_id`   | Satu `request_id` hanya boleh punya satu feedback (upsert). |
| foreign key `request_id`                       | FK            | `request_id`   | Referensi ke `interaction_logs(request_id)`, `on delete cascade`. |

**Access control:** RLS aktif, hanya `service_role` yang punya akses penuh (policy `Allow service_role all on response_feedback`).

**Retensi:** tidak independen — mengikuti retensi `interaction_logs` induknya melalui `on delete cascade` (maksimal 90 hari).

---

## `document_status`

Melacak status ingest setiap dokumen, termasuk state versioning (khusus kategori Pricelist).

| Column               | Type          | Nullable | Default    | Description                                                                 |
| --------------------- | -------------- | -------- | ----------- | ---------------------------------------------------------------------------- |
| `document_id`         | text           | No       | -           | Primary key. Format `{category}:{filename_tanpa_ekstensi}`.                  |
| `source`              | text           | No       | -           | Nama file asal di MinIO.                                                     |
| `category`            | text           | No       | -           | Kategori dokumen                     |
| `status`              | text           | No       | `'pending'` | `not_ingested` / `processing` / `success` / `failed`.                       |
| `detail`              | text           | Yes      | -           | Pesan tambahan, mis. alasan gagal.                                           |
| `last_ingested_at`    | timestamptz    | Yes      | -           | Waktu terakhir proses ingest selesai (`success` atau `failed`).              |
| `version_status`      | text           | No       | `'active'`  | `active` atau `superseded` (khusus dokumen versi lama yang digantikan).      |
| `superseded_by`       | text           | Yes      | -           | `document_id` versi baru yang menggantikan baris ini.                        |
| `superseded_at`       | timestamptz    | Yes      | -           | Waktu baris ditandai `superseded`.                                           |
| `created_at`          | timestamptz    | Yes      | `now()`     | Waktu baris pertama kali dibuat.                                             |

**Index:**

| Nama                                    | Kolom             |
| ------------------------------------------ | ------------------- |
| `idx_document_status_category`             | `category`           |
| `idx_document_status_status`               | `status`             |
| `idx_document_status_version`              | `version_status`     |

**Access control:** RLS aktif, hanya `service_role` (policy `Allow service_role all on document_status`, `select/insert/update/delete`).

Lihat juga [`versioning.md`](../kebijakan/versioning.md) untuk alur lengkap `version_status`, `superseded_by`, dan `superseded_at`.

---

## `ingestion_logs`

Mencatat hasil setiap proses ingest (per dokumen), termasuk jumlah chunk yang berhasil/gagal.

| Column               | Type            | Nullable | Default    | Description                                          |
| --------------------- | ---------------- | -------- | ----------- | ---------------------------------------------------------- |
| `id`                  | bigint            | No       | identity    | Primary key.                                                |
| `document_id`         | text              | No       | -           | Dokumen yang di-ingest.                                     |
| `category`            | text              | No       | -           | Kategori dokumen.                                           |
| `filename`            | text              | No       | -           | Nama file yang di-ingest.                                   |
| `total_chunks`        | int               | Yes      | 0           | Total chunk hasil chunking pada proses ini.                 |
| `chunks_inserted`     | int               | Yes      | 0           | Jumlah chunk baru yang di-insert.                           |
| `chunks_updated`      | int               | Yes      | 0           | Jumlah chunk existing yang di-update (fingerprint berubah). |
| `chunks_skipped`      | int               | Yes      | 0           | Jumlah chunk yang dilewati (fingerprint tidak berubah).     |
| `chunks_deleted`      | int               | Yes      | 0           | Jumlah chunk stale yang dihapus.                            |
| `chunks_failed`       | int               | Yes      | 0           | Jumlah chunk yang gagal diproses (mis. gagal embed/upsert). |
| `parse_error`         | text              | Yes      | -           | Pesan error jika parsing dokumen gagal total.               |
| `status`              | text              | No       | -           | `success` atau `failed`.                                    |
| `duration_seconds`    | numeric(10,3)     | Yes      | -           | Durasi proses ingest.                                       |
| `created_at`          | timestamptz       | Yes      | `now()`     | Waktu log dibuat.                                            |

**Index:**

| Nama                                     | Kolom             |
| ------------------------------------------- | ------------------- |
| `idx_ingestion_logs_category`               | `category`           |
| `idx_ingestion_logs_created_at`             | `created_at`         |
| `idx_ingestion_logs_document_id`            | `document_id`        |

**Access control:** hanya `service_role` (`insert`, `select`).

---

## `document_flags`

Menyimpan hasil screening dokumen (duplikat, rahasia, usang) yang dijalankan sebelum ingest (lihat [`screening.md`](../kebijakan/screening.md)).

| Column           | Type          | Nullable | Default    | Description                                                                 |
| ----------------- | -------------- | -------- | ----------- | ---------------------------------------------------------------------------- |
| `document_id`     | text           | No       | -           | Primary key, dokumen yang diperiksa.                                         |
| `flag_type`       | text           | No       | -           | `duplicate` / `stale` / `confidential` / `expired` / `clean`.                |
| `detail`          | text           | Yes      | -           | Detail temuan, mis. pattern yang cocok.                                      |
| `duplicate_of`    | text           | Yes      | -           | `document_id` lain jika `flag_type = 'duplicate'`.                          |
| `file_hash`       | text           | Yes      | -           | SHA-256 dari isi file, dipakai untuk deteksi duplikat.                       |
| `created_at`      | timestamptz    | Yes      | `now()`     | Waktu flag dicatat.                                                          |

**Index:**

| Nama                              | Kolom          |
| ----------------------------------- | --------------- |
| `idx_document_flags_type`           | `flag_type`      |

**Access control:** RLS aktif, hanya `service_role` (policy `Allow service_role all on document_flags`, akses penuh).

---

## `sessions`

Menyimpan metadata session percakapan chatbot, menggantikan in-memory store agar persist antar restart aplikasi dan mendukung sidebar riwayat percakapan pada widget chat (lihat [`session.md`](../kebijakan/session.md)).

| Column                 | Type        | Nullable | Default   | Description                                                        |
| ----------------------- | ----------- | -------- | ---------- | -------------------------------------------------------------------- |
| `session_id`            | text        | No       | -          | Primary key, UUID v4.                                                |
| `user_id`               | text        | Yes      | -          | Identifier user jika authentication tersedia; `null` untuk widget publik. |
| `title`                 | text        | Yes      | -          | Judul percakapan, diambil otomatis dari potongan pertanyaan pertama user. |
| `created_at`            | timestamptz | No       | `now()`    | Waktu session dibuat.                                                 |
| `last_activity_at`      | timestamptz | No       | `now()`    | Waktu aktivitas terakhir, diperbarui setiap request valid.            |
| `expires_at`            | timestamptz | No       | -          | Batas idle timeout (30 menit sejak `last_activity_at`).               |
| `absolute_expires_at`   | timestamptz | No       | -          | Batas absolute timeout (24 jam sejak `created_at`).                   |

**Index:**

| Nama                              | Kolom               |
| ----------------------------------- | --------------------- |
| `idx_sessions_last_activity`        | `last_activity_at`     |

**Access control:** RLS aktif, hanya `service_role` (policy `Allow service_role all on sessions`, akses penuh). Tidak ada validasi ownership berbasis `user_id` pada endpoint saat ini — siapa pun yang mengetahui `session_id` dapat mengambil atau menghapus session tersebut (lihat [Batasan & Risiko](../kebijakan/session.md#10-security--privacy)).

**Retensi:** mengikuti idle timeout 30 menit / absolute timeout 24 jam, dihapus melalui `SupabaseSessionStore.cleanup()`.

---

## `session_messages`

Menyimpan riwayat pesan (user & assistant) per session, digunakan untuk conversation history, contextualizer, dan load ulang percakapan dari sidebar.

| Column       | Type        | Nullable | Default   | Description                                                  |
| ------------- | ----------- | -------- | ---------- | ---------------------------------------------------------------- |
| `id`          | bigint      | No       | identity   | Primary key.                                                     |
| `session_id`  | text        | No       | -          | Foreign key ke `sessions.session_id`, `on delete cascade`.       |
| `role`        | text        | No       | -          | `user` atau `assistant` (`check constraint`).                    |
| `content`     | text        | No       | -          | Isi pesan.                                                       |
| `sources`     | jsonb       | Yes      | -          | Metadata dokumen yang dirujuk (khusus pesan `assistant`); `null` untuk pesan `user` atau jawaban fallback. |
| `created_at`  | timestamptz | No       | `now()`    | Waktu pesan dibuat, dipakai untuk urutan conversation.           |

**Index:**

| Nama                                    | Kolom                       |
| ------------------------------------------ | ----------------------------- |
| `idx_session_messages_session_id`          | `session_id, created_at`       |

**Access control:** RLS aktif, hanya `service_role` (policy `Allow service_role all on session_messages`, akses penuh).

**Retensi:** dihapus otomatis mengikuti penghapusan `sessions` induknya melalui `on delete cascade` (baik karena expiry maupun penghapusan manual oleh user melalui sidebar).

---

## Function

### `match_documents(query_embedding, match_count default 5)`

Pencarian semantic sederhana berbasis cosine similarity terhadap `documents.embedding`. Mengembalikan `id`, `content`, `metadata`, dan `similarity` (`1 - cosine_distance`), diurutkan dari yang paling mirip. Tidak melakukan filter kategori — dipertahankan sebagai utility function dasar, bukan yang dipakai oleh endpoint `/api/chat` (yang memakai `hybrid_search`).

### `hybrid_search(query_text, query_embedding, match_count default 10, full_text_weight default 1, semantic_weight default 1, rrf_k default 10, category_filter default null)`

Function utama yang dipakai `rag/retriever.py` untuk retrieval. Menggabungkan hasil **full-text search** (`ts_rank_cd` pada kolom `fts`, dengan fallback dari `websearch_to_tsquery` ke `to_tsquery` OR-token jika query kosong hasilnya) dan **semantic search** (`embedding <=> query_embedding`) menggunakan **Reciprocal Rank Fusion (RRF)**:

```text
hybrid_score = (1 / (rrf_k + rank_fulltext)) * full_text_weight
             + (1 / (rrf_k + rank_semantic)) * semantic_weight
```

`category_filter` (array kategori) diterapkan pada kedua sisi (full-text dan semantic) sebelum fusion, sehingga chunk dari kategori yang tidak diizinkan tidak pernah ikut proses scoring — mendukung RBAC content filtering (lihat [`rbac-policy.md`](../kebijakan/rbac-policy.md)). Mengembalikan `id`, `content`, `metadata`, `chunk_index`, `embedding`, `hybrid_score`.

### `delete_expired_interaction_logs()`

`security definer` function untuk scheduled cleanup. Menghapus baris `interaction_logs` yang:
- tidak punya feedback terkait dan berumur > 30 hari, **atau**
- punya feedback terkait dan berumur > 90 hari.

Mengembalikan jumlah baris yang dihapus (`integer`). Akses `execute` dicabut dari `anon`/`authenticated`, hanya dipanggil oleh service backend (lihat `sync/retention.py`).

### `get_top_faq(days default 30, result_limit default 5)`

Mengagregasi `interaction_logs` dalam rentang `days` hari terakhir, mengelompokkan berdasarkan teks `query` yang identik, lalu mengembalikan `query`, `total_queries` (jumlah kemunculan), dan `last_asked` (waktu terakhir ditanyakan), diurutkan dari yang paling sering. Dipakai oleh endpoint `GET /api/logs/top-faq`.

### `get_ingestion_report(start_date default current_date - 7, end_date default current_date)`

Mengagregasi `ingestion_logs` per `category` dalam rentang tanggal tertentu: total run, total chunk inserted/updated/skipped/deleted/failed, dan jumlah run yang berstatus `failed`. Digunakan untuk kebutuhan monitoring kualitas proses ingestion (belum diekspos sebagai endpoint API pada dokumentasi saat ini).

### `get_problematic_answers(days default 30, min_downvotes default 1, result_limit default 20)`

Menggabungkan `interaction_logs` dan `response_feedback` untuk mencari jawaban dengan downvote terbanyak dalam rentang `days` hari, dengan ambang minimum `min_downvotes`. Mengembalikan `request_id`, `question`, `answer`, `sources`, `upvotes`, `downvotes`, `reasons` (array alasan downvote), dan `last_feedback_at`, diurutkan dari downvote terbanyak. Dipakai oleh endpoint `GET /api/analytics/problematic-answers`.

### `get_flagged_documents(days default 30, result_limit default 20)`

Meng-unnest array `sources` pada setiap `interaction_logs` yang memiliki feedback, mengelompokkan berdasarkan `source` dan `chunk_index`, lalu menghitung `flagged_count` (jumlah downvote), `total_referenced_count` (total kemunculan pada jawaban berfeedback), dan `flag_ratio` (`flagged_count / total_referenced_count`, dibulatkan 2 desimal). Hanya menampilkan kombinasi yang punya minimal 1 downvote. Digunakan untuk mengidentifikasi dokumen yang berpotensi perlu direvisi, dipakai oleh endpoint `GET /api/analytics/flagged-documents`.

---

## Ringkasan Function

| Function                              | Dipanggil oleh                              | Akses eksekusi         |
| --------------------------------------- | --------------------------------------------- | ------------------------ |
| `match_documents()`                     | (utility, tidak dipakai langsung oleh route)  | -                         |
| `hybrid_search()`                       | `rag/retriever.py`                            | anon (default RLS)       |
| `delete_expired_interaction_logs()`     | `sync/retention.py`                           | service_role saja        |
| `get_top_faq()`                         | `GET /api/logs/top-faq`                       | service_role saja        |
| `get_ingestion_report()`                | (belum ada endpoint API)                      | service_role saja        |
| `get_problematic_answers()`             | `GET /api/analytics/problematic-answers`      | service_role saja        |
| `get_flagged_documents()`               | `GET /api/analytics/flagged-documents`        | service_role saja        |
