# Dashboard Dokumen

Dashboard dokumen digunakan oleh Admin untuk mengelola file knowledge base yang tersimpan di MinIO dan mengatur proses indexing ke Supabase/pgvector.

Dashboard tersedia pada:

```text
/dashboard
```

Frontend dashboard menggunakan Vanilla HTML, CSS, dan JavaScript.

## Upload Dokumen

User dapat:

1. Memilih file.
2. Memilih category.
3. Mengupload file.
4. File disimpan ke MinIO menggunakan struktur:

```text
knowledge-expert/
├── sop/
│   └── example.pdf
├── datasheet/
│   └── product.pdf
└── pricelist/
    └── price.xlsx
```

Category yang digunakan:

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

Jika file dengan nama dan category yang sama sudah ada di MinIO, dashboard meminta konfirmasi sebelum melakukan replace.

## Daftar Dokumen

Dashboard menampilkan:

```text
Filename
Category
Size
Upload time
Ingest status
Last ingest time
Action
```

Waktu ditampilkan dalam zona waktu:

```text
WIB (UTC+7)
```

Status ingest:

```text
not_ingested
processing
success
failed
```

Contoh:

```text
example.pdf
Category       : datasheet
Uploaded       : 2026-09-08 09:30:00 WIB
Status         : success
Last ingested  : 2026-09-08 09:35:00 WIB
```

Status berasal dari tabel `document_status` pada Supabase.

## Ingest Dokumen

Dokumen yang sudah tersimpan di MinIO dapat di-ingest secara individual melalui dashboard.

Flow:

```text
MinIO
   ↓
Ingest
   ↓
Download temporary file
   ↓
Preprocessing
   ↓
Document Loader
   ↓
StructureAwareChunker
   ↓
Fingerprint
   ↓
BGE-M3
   ↓
Supabase / pgvector
```

Ingest dijalankan secara asynchronous menggunakan background thread.

Status akan berubah:

```text
not_ingested
      ↓
processing
      ↓
success
```

Jika terjadi error:

```text
processing
      ↓
failed
```

Dashboard melakukan refresh status secara berkala sehingga perubahan status ingest dapat terlihat tanpa menjalankan command manual.

## Un-ingest Dokumen

Un-ingest digunakan untuk menghapus hasil indexing tanpa menghapus file sumber dari MinIO.

```text
Un-ingest

MinIO
   ↓
File tetap ada

Supabase / pgvector
   ↓
Vector chunks dihapus

document_status
   ↓
Status dihapus
```

Setelah un-ingest, dokumen kembali berstatus:

```text
not_ingested
```

File tetap tersedia di MinIO dan dapat di-ingest kembali.

## Hapus Dokumen

Hapus dokumen digunakan untuk menghapus file sumber dan seluruh data indexing-nya.

```text
Delete

MinIO
   ↓
File dihapus

Supabase / pgvector
   ↓
Vector chunks dihapus

document_status
   ↓
Status dihapus
```

Dengan demikian tidak terdapat dokumen vector yang berasal dari file yang sudah tidak tersedia di MinIO.

## Replace Dokumen

Jika user mengupload file dengan nama yang sama pada category yang sama, dashboard akan meminta konfirmasi replace.

Proses replace harus menghapus hasil indexing lama sebelum file baru digunakan:

```text
Existing file
      ↓
Delete old vectors
      ↓
Delete old document status
      ↓
Replace file in MinIO
      ↓
not_ingested
      ↓
Ingest new file
```

Hal ini mencegah vector dari versi lama dan versi baru berada bersamaan di vector database.

Untuk kategori **Pricelist**, replace dan versioning mengikuti aturan khusus — lihat [`versioning.md`](../kebijakan/versioning.md).

## Endpoint Dashboard

| Method   | Endpoint                      | Fungsi                            |
| -------- | ------------------------------ | ---------------------------------- |
| `POST`   | `/api/admin/documents/upload` | Upload atau replace file          |
| `GET`    | `/api/admin/documents`        | Menampilkan daftar dokumen        |
| `POST`   | `/api/admin/ingest`           | Ingest dokumen                    |
| `POST`   | `/api/admin/un-ingest`        | Menghapus hasil indexing          |
| `DELETE` | `/api/admin/documents/delete` | Menghapus file dan hasil indexing |

Semua endpoint membutuhkan role:

```text
Admin
```

Detail request/response setiap endpoint di atas tersedia pada [`admin-endpoints.md`](admin-endpoints.md).

## Source of Truth

Arsitektur document management menggunakan pembagian tanggung jawab:

```text
MinIO
  = Source document

Supabase / pgvector
  = Indexed representation

document_status
  = Ingestion state
```

MinIO menyimpan file asli, sedangkan Supabase/pgvector menyimpan chunk dan embedding yang digunakan oleh sistem retrieval.