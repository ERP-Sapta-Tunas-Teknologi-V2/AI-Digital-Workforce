# Admin Endpoints

Sync dan ingest tersedia sebagai endpoint API untuk kebutuhan operasional.

Akses endpoint dibatasi untuk role:

```text
Admin
```

## Upload Dokumen

```http
POST /api/admin/documents/upload
Content-Type: multipart/form-data
```

Form fields:

| Field      | Required | Description                                  |
| ---------- | -------- | --------------------------------------------- |
| `file`     | ya       | File yang diupload                            |
| `category` | ya       | Salah satu dari kategori di [Sync satu category](#sync-satu-category) |
| `replace`  | tidak    | `true` untuk menimpa file yang sudah ada      |
| `supersedes` | tidak  | Khusus kategori **Pricelist**: nama file lama yang digantikan versi baru ini (Skenario B pada [`versioning.md`](../kebijakan/versioning.md)) |

Untuk kategori pada `VERSIONED_CATEGORIES` (saat ini: `pricelist`), upload menjalankan deteksi versi otomatis:

- **Nama file sama + `replace=true`**: file lama diarsipkan (`_archive/`), status lama ditandai `superseded`.
- **Nama file berbeda + `supersedes` diisi**: dokumen yang disebutkan di `supersedes` ditandai `superseded`, vector lama dihapus.
- **Nama file berbeda + `supersedes` kosong**: jika hanya ada satu versi aktif di kategori tsb, otomatis dijadikan `superseded`. Jika lebih dari satu, request ditolak `409` dengan daftar `active_versions`.

Jika berhasil:

```json
 {
   "message": "File uploaded successfully",
   "category": "datasheet",
-  "filename": "example.pdf"
+  "filename": "example.pdf",
+  "document_id": "datasheet:example",
+  "superseded": null
 }
```

Jika dokumen di-flag saat screening (lihat [`screening.md`](../kebijakan/screening.md)), response `200 OK` (bukan `201`):

```json
{
  "warning": "document flagged for review",
  "flags": [{"type": "duplicate", "detail": "..."}],
  "message": "File di-upload tetapi review diperlukan sebelum di-ingest karena \"...\"."
}
```

Jika ditemukan lebih dari satu versi aktif pada kategori bervariasi tanpa `supersedes` eksplisit:

```json
{
  "error": "multiple active versions found, specify 'supersedes' explicitly",
  "active_versions": ["pricelist:dell_2025", "pricelist:dell_2026"]
}
```

Status code: `409 Conflict`.

## Daftar Dokumen

```http
GET /api/admin/documents?category=datasheet
```

Parameter `category` bersifat opsional; jika tidak dikirim, menampilkan seluruh kategori.

Response menampilkan setiap file beserta waktu upload dan status ingest, dalam zona waktu WIB:

```json
[
  {
    "category": "datasheet",
    "filename": "example.pdf",
    "path": "datasheet/example.pdf",
    "document_id": "datasheet:example",
    "uploaded_at": "2026-09-08T02:30:00+00:00",
    "uploaded_at_wib": "2026-09-08 09:30:00 WIB",
    "ingest_status": "success",
    "last_ingested_at": "2026-09-08T02:35:00+00:00",
    "last_ingested_at_wib": "2026-09-08 09:35:00 WIB",
    "size": 245678
  }
]
```

Nilai `ingest_status` yang mungkin muncul:

```text
not_ingested
processing
success
failed
```

`ingest_status` diambil dari tabel `document_status` dan dicocokkan berdasarkan `document_id`.

## Ingest Endpoint

Digunakan setelah dokumen sudah tersimpan di sistem, misalnya melalui proses upload terpisah.

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

File harus sudah tersimpan di MinIO pada bucket dan kategori yang bersangkutan. Jika file tidak ditemukan di storage, response `404 Not Found`.

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

## Un-ingest Endpoint

Endpoint ini menghapus hasil indexing dokumen dari Supabase/pgvector tanpa menghapus file dari MinIO.

```http
POST /api/admin/un-ingest
Content-Type: application/json
```

Body:

```json
{
  "category": "datasheet",
  "filename": "example.pdf"
}
```

Response:

```json
{
  "message": "Document un-ingested successfully",
  "document_id": "datasheet:example"
}
```

Status code:

```text
200 OK
```

## Delete Document Endpoint

Endpoint ini menghapus file dari MinIO dan hasil indexing dari Supabase/pgvector.

```http
DELETE /api/admin/documents/delete
Content-Type: application/json
```

Body:

```json
{
  "category": "datasheet",
  "filename": "example.pdf"
}
```

Response:

```json
{
  "message": "Document deleted successfully",
  "category": "datasheet",
  "filename": "example.pdf"
}
```

Status code:

```text
200 OK
```

Jika file tidak ditemukan di MinIO:

```text
404 Not Found
```

## Download Dokumen

```http
GET /api/admin/documents/download?category=datasheet&filename=example.pdf
```

Response: file stream dengan `Content-Disposition: attachment`.

### Error Response

`404 Not Found` — file tidak ditemukan di storage:

```json
{ "error": "file not found in storage" }
```

## Document Lifecycle

Lifecycle dokumen:

```text
                    Upload
                       │
                       ▼
                     MinIO
                       │
                       ▼
                 not_ingested
                       │
                       │ Ingest
                       ▼
                   processing
                    /       \
                   /         \
                  ▼           ▼
              success       failed
                  │
                  │
            Un-ingest
                  │
                  ▼
             not_ingested
```

Delete dari dashboard:

```text
             MinIO
                │
                ▼
             DELETE
                │
                ├──────────────┐
                ▼              ▼
       Supabase / pgvector   document_status
                │              │
                ▼              ▼
              DELETE         DELETE
```

File yang dihapus dari MinIO tidak boleh tetap memiliki vector representation di Supabase/pgvector.

## Sync Endpoint

Endpoint ini digunakan untuk melakukan sinkronisasi seluruh dokumen atau hanya satu category.

```http
POST /api/admin/sync
Content-Type: application/json
```

### Sync seluruh category

Kirim body kosong:

```json
{}
```

Proses akan melakukan sync terhadap:

```text
documents/
```

Response:

```json
{
  "message": "sync started for all categories"
}
```

### Sync satu category

Contoh:

```json
{
  "category": "datasheet"
}
```

Category yang diperbolehkan:

```text
general
sop
pricelist
case
meeting
training
solution
proposal
guide
competitive
datasheet
sow
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

## Log Export

```http
GET /api/logs/export?start=YYYY-MM-DD&end=YYYY-MM-DD
```

Akses dibatasi untuk role `Admin`.

Filter tanggal menggunakan format `YYYY-MM-DD`.

Contoh:

```text
/api/logs/export?start=YYYY-MM-DD&end=YYYY-MM-DD
```

Export menggunakan CSV UTF-8 BOM.

Detail request/response lengkap tersedia pada [`api-contract.md`](api-contract.md).