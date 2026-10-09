# Dashboard Dokumen

Dashboard digunakan oleh Admin untuk mengelola file knowledge base yang tersimpan di MinIO, mengatur proses indexing ke Supabase/pgvector, menyetujui dokumen untuk chatbot, dan memantau kualitas jawaban.

Dashboard utama adalah frontend Vue pada route:

```text
/digital-workforce/dashboard
```

(menu **Dashboard** pada sidebar chat). Flask juga masih menyajikan dashboard statis lama (Vanilla HTML/CSS/JS) pada `/dashboard`; dokumen ini mengacu pada dashboard Vue. Detail frontend: [`frontend.md`](../referensi-teknis/frontend.md).

## Panel

| Panel (komponen)                        | Fungsi |
| --------------------------------------- | ------ |
| Ringkasan (`DashboardOverview`)         | Periode 7/14/30/90 hari; total query, total feedback, % feedback positif, jumlah dokumen teratas; grafik volume query; tabel dokumen paling sering dirujuk (`dashboard-summary`) |
| Dokumen (`DashboardDocument`)           | Upload, approve/revoke, ingest, un-ingest, unduh, hapus |
| Top FAQ (`DashboardTopFaq`)             | `GET /api/logs/top-faq` (rentang 7/14/30/90 hari, limit 5) |
| Jawaban Bermasalah (`DashboardProblematic`) | `GET /api/analytics/problematic-answers` (min. downvote bebas diisi; klik baris untuk melihat jawaban dan alasan) |
| Dokumen Ditandai (`DashboardFlagged`)   | `GET /api/analytics/flagged-documents` (rasio ≥ 0,5 merah, ≥ 0,2 kuning) |
| Export Log (`DashboardExport`)          | `GET /api/logs/export` dengan rentang tanggal start/end → `interaction_logs.csv` |

## Akses & Role

Setiap request dashboard mengirim `X-User-Role` dari role AI akun yang login (`getRoleHeader()`, bukan hardcode). Akun non-Admin mendapat `403` pada `/api/admin/*`. Endpoint `/api/logs/*` dan `/api/analytics/*` belum dibatasi (lihat [`rbac-policy.md`](../kebijakan/rbac-policy.md)).

## Upload Dokumen

User dapat:

1. Memilih file.
2. Memilih category.
3. (Opsional) mengisi metadata dan opsi replace/supersedes.
4. Mengupload file.

File disimpan ke MinIO dengan struktur:

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

Field pada dialog upload:

| Field | Keterangan |
| ----- | ---------- |
| File, Category | Wajib |
| Replace jika sudah ada | Menimpa file dengan nama sama. Tanpa ini server membalas `409`, dan dialog menampilkan tombol **Ya, Replace** |
| Supersedes filename | Opsional, khusus Pricelist dengan nama file baru yang berbeda (lihat [`versioning.md`](../kebijakan/versioning.md)) |
| Content type, Industri, Persona, Kompetitor, Tanggal efektif | Metadata opsional (lihat [`admin-endpoints.md`](admin-endpoints.md#metadata-dokumen)) |

Jika dokumen ter-flag saat screening (duplicate/confidential), file tetap tersimpan dan dialog menampilkan peringatan; dokumen tidak bisa di-ingest sebelum diperbaiki (lihat [`screening.md`](../kebijakan/screening.md)).

## Daftar Dokumen

Dashboard menampilkan:

```text
Filename
Category
Status
Approval
Version
Flags
Uploaded (WIB)
Last Ingested (WIB)
Action
```

Aksi (menu titik tiga): **Approve** / **Revoke**, **Ingest** / **Un-ingest** (bergantung status), **Download**, **Delete** (dengan konfirmasi). Tombol **Sync** pada panel dikomentari (disembunyikan); sync dijalankan melalui API.

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

Status approval: `pending`, `approved`, `rejected`, serta `expired` bila melewati `expires_at`. Kolom Version menampilkan `active` atau `superseded`. Dokumen di `_archive/` ditandai arsip.

Contoh:

```text
example.pdf
Category       : datasheet
Uploaded       : 2026-09-08 09:30:00 WIB
Status         : success
Approval       : approved
Last ingested  : 2026-09-08 09:35:00 WIB
```

Status berasal dari tabel `document_status` pada Supabase.

## Approval Dokumen

Chatbot hanya memakai dokumen yang **sudah di-ingest dan `approved`**, `active`, serta belum expired (filter pada `hybrid_search`). Dokumen baru berstatus `pending`.

```text
Upload → Ingest (success) → Approve → dipakai chatbot
```

* **Approve** ditolak (`409`) untuk dokumen ber-flag `duplicate`/`confidential`.
* **Revoke** mengubah status menjadi `rejected`; vector tidak dihapus tetapi tidak ikut pencarian.
* Urutan Ingest dan Approve bebas; keduanya wajib terpenuhi.
* Dialog dashboard belum mengirim `expires_at`; gunakan API bila dokumen perlu kedaluwarsa otomatis.

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

Dashboard me-refresh daftar sekali ±1,5 detik setelah ingest dimulai. Tidak ada polling; status selanjutnya (`success`/`failed`) dilihat dengan menekan tombol refresh pada panel.

## Un-ingest Dokumen

Un-ingest menghapus hasil indexing tanpa menghapus file sumber dari MinIO.

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
Row dihapus (termasuk approval dan doc_metadata)
```

Setelah un-ingest, dokumen kembali berstatus `not_ingested`. Untuk dipakai lagi: Ingest ulang, lalu **Approve** ulang (dan isi ulang metadata bila ada).

## Hapus Dokumen

Hapus dokumen menghapus file sumber dan seluruh data indexing-nya.

```text
Delete

MinIO
   ↓
File dihapus

Supabase / pgvector
   ↓
Vector chunks dihapus

document_status + document_flags
   ↓
Dihapus
```

Dengan demikian tidak terdapat dokumen vector yang berasal dari file yang sudah tidak tersedia di MinIO.

## Replace Dokumen

Jika user mengupload file dengan nama yang sama pada category yang sama dengan opsi **Replace jika sudah ada**:

**Non-versioned (semua kategori selain Pricelist):**

```text
Upload dengan "Replace jika sudah ada"
      ↓
File di MinIO ditimpa
      ↓
Screening dijalankan ulang
      ↓
approval_status → pending
```

Vector dan status ingest lama **tidak** dihapus, tetapi dokumen **tidak dipakai chatbot** sampai di-approve ulang. Setelah di-approve, chatbot memakai isi lama sampai admin menekan **Ingest** (chunk yang fingerprint-nya sama dilewati, chunk usang dihapus). Langkah yang benar: Upload → Ingest → Approve.

**Pricelist:** replace dan versioning mengikuti aturan khusus — lihat [`versioning.md`](../kebijakan/versioning.md).

## Endpoint Dashboard

| Method   | Endpoint                        | Fungsi                                |
| -------- | ------------------------------- | ------------------------------------- |
| `POST`   | `/api/admin/documents/upload`   | Upload atau replace file (+ metadata) |
| `GET`    | `/api/admin/documents`          | Menampilkan daftar dokumen            |
| `POST`   | `/api/admin/documents/approval` | Approve / revoke dokumen              |
| `POST`   | `/api/admin/documents/metadata` | Mengubah metadata dokumen             |
| `POST`   | `/api/admin/ingest`             | Ingest dokumen                        |
| `POST`   | `/api/admin/un-ingest`          | Menghapus hasil indexing              |
| `DELETE` | `/api/admin/documents/delete`   | Menghapus file dan hasil indexing     |
| `GET`    | `/api/admin/documents/download` | Mengunduh file sumber                 |
| `POST`   | `/api/admin/sync`              | Sinkronisasi (belum ada tombol di UI) |

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
  = Ingestion state, approval, versioning, doc_metadata
```

MinIO menyimpan file asli, sedangkan Supabase/pgvector menyimpan chunk dan embedding yang digunakan oleh sistem retrieval.
