# Indexing & Sinkronisasi Dokumen

## Indexing Dokumen

Format dokumen yang didukung:

```text
.pdf
.docx
.xlsx
.pptx
```

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

Alur preprocessing per format:

| Format | Alur |
| ------ | ---- |
| `.pdf`  | pymupdf4llm → Markdown per halaman → Docling |
| `.docx` | LibreOffice (headless) → PDF → pymupdf4llm → Docling |
| `.pptx` | python-pptx (teks, tabel → Markdown, grouped shape, speaker notes per slide) → Docling |
| `.xlsx` | Docling langsung (tanpa Markdown) |

Setelah chunking: Fingerprint → BGE-M3 → Supabase/pgvector.

Untuk melakukan indexing manual satu file:

```bash
python ingest.py <category> <filename>
# contoh: python ingest.py datasheet example.pdf
```

File harus sudah ada di MinIO pada `{category}/{filename}`.

Catatan:

* Saat chunking, teks yang cocok `INJECTION_PATTERNS` diganti `[REDACTED]`. Pola longgar seperti `act as`, `pretend`, `disregard` bisa mengubah isi dokumen teknis yang sah.
* `document_id = {category}:{nama_tanpa_ekstensi}`. `a.pdf` dan `a.docx` di kategori yang sama **bertabrakan**.
* Ekstraksi gambar (`describe_image`) saat ini dinonaktifkan (dikomentari di `cleaner.py`).
* Metadata chunk menyertakan `updated_at` (modifikasi file di MinIO) dan metadata dokumen opsional dari `document_status.doc_metadata` (lihat [`admin-endpoints.md`](admin-endpoints.md#metadata-dokumen)).
* Ingest/sync tidak meng-approve dokumen. Chatbot hanya memakai dokumen berstatus `approved` dan `active` (lihat [`dashboard.md`](dashboard.md)).

Untuk indexing dokumen individual yang sudah tersimpan di MinIO, gunakan endpoint `/api/admin/ingest` (lihat [`admin-endpoints.md`](admin-endpoints.md)) atau Dashboard Dokumen (lihat [`dashboard.md`](dashboard.md)).

## Sinkronisasi Dokumen

Sinkronisasi membandingkan dokumen sumber pada MinIO dengan data yang terdapat di vector database.

Struktur penyimpanan (bucket `knowledge-expert`):

```text
knowledge-expert/
├── sop/
├── datasheet/
└── pricelist/
```

Setiap kategori merupakan prefix folder pada bucket MinIO, bukan direktori filesystem lokal.

Sinkronisasi tersedia melalui endpoint:

```http
POST /api/admin/sync
```

Tidak terdapat proses sync manual melalui command `python`. Operasional sinkronisasi dilakukan melalui API.

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

Dokumen yang sudah tidak terdapat pada source akan dihapus dari vector database berdasarkan `document_id`. Sync tidak mengubah `approval_status`.

Untuk operasi individual, gunakan Dashboard Dokumen:

```text
Upload
Ingest
Un-ingest
Delete
```

Detail endpoint sync tersedia pada [`admin-endpoints.md`](admin-endpoints.md#sync-endpoint).
