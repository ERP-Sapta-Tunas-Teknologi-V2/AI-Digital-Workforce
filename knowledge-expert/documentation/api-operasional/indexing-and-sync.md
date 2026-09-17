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

Untuk melakukan indexing:

```bash
python ingest.py
```

Gunakan proses ini untuk indexing dokumen secara manual.

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

Dokumen yang sudah tidak terdapat pada source akan dihapus dari vector database berdasarkan `document_id`.

Untuk operasi individual, gunakan Dashboard Dokumen:

```text
Upload
Ingest
Un-ingest
Delete
```

Detail endpoint sync tersedia pada [`admin-endpoints.md`](admin-endpoints.md#sync-endpoint).
