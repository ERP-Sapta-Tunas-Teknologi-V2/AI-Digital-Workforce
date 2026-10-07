# Dashboard Dokumen

Dashboard dokumen digunakan oleh Admin untuk mengelola file knowledge base yang tersimpan di MinIO dan mengatur proses indexing ke Supabase/pgvector.

Dashboard tersedia pada:

```text
/dashboard
```

Frontend dashboard menggunakan Vanilla HTML, CSS, dan JavaScript.

Dashboard memiliki 5 halaman:

| Menu               | Fungsi                                                                 |
| ------------------ | ---------------------------------------------------------------------- |
| Ringkasan          | Total pertanyaan, total feedback, % feedback positif, grafik volume, dokumen paling sering dirujuk (`dashboard-summary`) |
| Dokumen            | Upload, ingest, un-ingest, unduh, hapus, Sync Semua                    |
| Top FAQ            | `GET /api/logs/top-faq` (rentang 7/30/90 hari, jumlah 5/10/20)         |
| Jawaban Bermasalah | `GET /api/analytics/problematic-answers` (min. downvote 1–3)           |
| Dokumen Ditandai   | `GET /api/analytics/flagged-documents`                                 |

Tombol **Ekspor Log CSV** tersedia di topbar (`GET /api/logs/export`).

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

Jika file sudah ada, server membalas `409`. User harus mencentang **Ganti jika sudah ada** lalu upload ulang. Dashboard belum mengirim parameter `supersedes` (khusus Pricelist dengan banyak versi aktif, gunakan API langsung).

## Daftar Dokumen

Dashboard menampilkan:

```text
Nama File
Kategori
Status
Versi
Flags
Diunggah
Terakhir Ingest
Aksi
```

Aksi: Ingest, Un-ingest, Unduh, Hapus. Status tambahan: `superseded`. Badge `arsip` ditampilkan untuk file di `_archive/`.

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

Dashboard me-refresh daftar sekali ±1,5 detik setelah ingest dimulai. Tidak ada polling; status selanjutnya (`success`/`failed`) dilihat dengan membuka ulang halaman Dokumen atau mengganti filter/tab.

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

Jika user mengupload file dengan nama yang sama pada category yang sama dengan opsi **Ganti jika sudah ada**:

**Non-versioned (semua kategori selain Pricelist):**

```text
Upload dengan "Ganti jika sudah ada"
      ↓
File di MinIO ditimpa
      ↓
Screening dijalankan ulang
```

Vector dan status lama **tidak** dihapus. Chatbot tetap memakai isi lama sampai admin menekan **Ingest** (chunk yang fingerprint-nya sama dilewati, chunk usang dihapus), dan status tetap `success` sampai saat itu.

**Pricelist:** replace dan versioning mengikuti aturan khusus — lihat [`versioning.md`](../kebijakan/versioning.md).

## Endpoint Dashboard

| Method   | Endpoint                      | Fungsi                            |
| -------- | ------------------------------ | ---------------------------------- |
| `POST`   | `/api/admin/documents/upload` | Upload atau replace file          |
| `GET`    | `/api/admin/documents`        | Menampilkan daftar dokumen        |
| `POST`   | `/api/admin/ingest`           | Ingest dokumen                    |
| `POST`   | `/api/admin/un-ingest`        | Menghapus hasil indexing          |
| `DELETE` | `/api/admin/documents/delete` | Menghapus file dan hasil indexing |
| `GET`    | `/api/admin/documents/download` | Mengunduh file sumber           |
| `POST`   | `/api/admin/sync`             | Sinkronisasi (tombol "Sync Semua") |

Semua endpoint membutuhkan role:

```text
Admin
```

> ⚠️ Dashboard saat ini mengirim `X-User-Role: Admin` secara hardcode (`ADMIN_ROLE_HEADER` di `dashboard.js`, ada TODO di kode).

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