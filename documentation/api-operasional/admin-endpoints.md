# Admin Endpoints

Sync dan ingest tersedia sebagai endpoint API untuk kebutuhan operasional.

Akses endpoint dibatasi untuk role:

```text
Admin
```

> ⚠️ `@require_role("Admin")` saat ini dikomentari pada seluruh endpoint di `admin.py`.

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
| `supersedes` | tidak  | Khusus kategori **Pricelist**: nama file lama yang digantikan versi baru ini (Cara 2, lihat [`versioning.md`](../kebijakan/versioning.md)) |

Jika file dengan nama yang sama sudah ada dan `replace` bukan `true`, response `409 Conflict`:

```json
{
  "exists": true,
  "message": "File 'example.pdf' already exists in category 'datasheet'. Replace it?"
}
```

Untuk kategori pada `VERSIONED_CATEGORIES` (saat ini: `pricelist`), upload menjalankan deteksi versi otomatis:

- **Nama file sama + `replace=true`** (Cara 1): file lama dipindah ke `{category}/_archive/{timestamp}_{filename}`; row status lama disalin sebagai `{category}:_archive_{timestamp}_{stem}` (mis. `pricelist:_archive_20260911151203_cisco`) dan ditandai `superseded`; row asli dihapus.
- **Nama file berbeda + `supersedes`** (Cara 2, eksplisit): vector lama dihapus, status lama `superseded`.
- **Nama file berbeda tanpa `supersedes`**: satu versi aktif → otomatis `superseded`; lebih dari satu → `409` + `active_versions`.

Untuk kategori non-versioned, `replace=true` hanya menimpa file di MinIO. Vector dan status lama tetap ada sampai dokumen di-ingest ulang.

Jika berhasil:

```json
{
  "message": "File uploaded successfully",
  "category": "datasheet",
  "filename": "example.pdf",
  "document_id": "datasheet:example",
  "superseded": null
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

Jika dokumen ter-flag, file tetap tersimpan dan proses versioning sudah dijalankan sebelum response `200 warning` dikirim.

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
    "size": 245678,
    "version_status": "active",
    "superseded_by": null,
    "approval_status": "approved",
    "expires_at": null,
    "is_expired": false,
    "is_archived": false,
    "flags": [{"type": "stale", "detail": "matched pattern: \\bdraft\\b", "duplicate_of": null}]
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

Nilai `approval_status`: `pending` (default), `approved`, `rejected`.

Endpoint ini juga menjalankan `reset_stale_processing()`: status `processing` yang lebih dari 15 menit diubah ke `failed`.

## Approval Dokumen

Mengatur status persetujuan dokumen. Hanya dokumen yang berstatus `approved`, `active`, dan belum kedaluwarsa yang ikut dicari oleh `hybrid_search`, jadi dokumen yang sudah di-ingest tetap tidak dipakai chatbot sebelum di-approve.

```http
POST /api/admin/documents/approval
Content-Type: application/json
```

Body:

```json
{
  "category": "datasheet",
  "filename": "example.pdf",
  "action": "approve",
  "expires_at": "2026-12-31"
}
```

| Field        | Required | Description                                                                                  |
| ------------ | -------- | --------------------------------------------------------------------------------------------- |
| `category`   | ya       | Salah satu dari 12 kategori (lihat [Sync satu category](#sync-satu-category))                |
| `filename`   | ya       | Nama file yang sudah ada di MinIO                                                             |
| `action`     | ya       | `approve` atau `reject`                                                                       |
| `expires_at` | tidak    | Format ISO (`YYYY-MM-DD` atau datetime). Hanya dipakai saat `approve`; diabaikan saat `reject` |

Response `200 OK`:

```json
{
  "message": "approved",
  "document_id": "datasheet:example"
}
```

Untuk `action = reject`, nilai `message` adalah `"rejected"`.

### Efek

| Action    | `approval_status` | `approved_by`                  | `approved_at` | `expires_at`          |
| --------- | ----------------- | ------------------------------ | ------------- | --------------------- |
| `approve` | `approved`        | header `X-User-Role`           | waktu sekarang (UTC) | nilai request (atau `null`) |
| `reject`  | `rejected`        | `null`                         | `null`        | `null`                |

* Jika row `document_status` belum ada (dokumen belum pernah di-ingest), row dibuat dengan `status = not_ingested`.
* Approval tidak memicu ingest, dan reject tidak menghapus vector. Vector tetap ada di `documents` tetapi tidak ikut pencarian.
* Upload ulang (`replace=true`) mengembalikan `approval_status` ke `pending` dan mengosongkan `approved_by` dan `approved_at`.
* Dokumen yang melewati `expires_at` ditampilkan sebagai `expired` di daftar dokumen (`is_expired: true`) dan tidak ikut pencarian.

### Error Response

`400 Bad Request`:

```json
{ "error": "category must be one of [...]" }
```
```json
{ "error": "filename is required" }
```
```json
{ "error": "action must be 'approve' or 'reject'" }
```
```json
{ "error": "expires_at must be ISO format" }
```

`404 Not Found`:

```json
{ "error": "file not found in storage" }
```

`409 Conflict`, jika `action = approve` dan dokumen ber-flag `duplicate` atau `confidential` (lihat [`screening.md`](../kebijakan/screening.md)):

```json
{ "error": "document flagged as ['duplicate'], cannot be approved" }
```

## Ingest Endpoint

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

Jika dokumen di-flag `duplicate` atau `confidential` pada screening (lihat [`screening.md`](../kebijakan/screening.md)), ingest diblokir:

```json
{
  "error": "document flagged as ['duplicate'], ingest blocked pending review"
}
```

Status code: `409 Conflict`. Saat ini tidak ada endpoint override; flag dihapus dengan upload ulang atau dengan menghapus dokumen.

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
                 not_ingested  (approval_status: pending)
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

Dokumen baru dipakai chatbot hanya setelah `success` ingest **dan** `approved`.

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

Sync membandingkan objek di bucket MinIO per kategori dengan `documents` di Supabase. Yang dilewati: file di `_archive/`, dokumen `superseded`, dan dokumen yang di-flag `duplicate`/`confidential` (log: `[SYNC] SKIPPED (flagged)`).

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