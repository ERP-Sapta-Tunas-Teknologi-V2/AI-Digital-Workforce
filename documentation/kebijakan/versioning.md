# Versioning Dokumen (Khusus Pricelist)

## Apa itu Versioning?

Setiap kali file **Pricelist** diganti dengan versi baru, sistem **tidak menghapus** versi lama. Versi lama disimpan otomatis sebagai arsip, dan versi baru menjadi satu-satunya yang aktif digunakan chatbot.

Fitur ini khusus berlaku untuk kategori **Pricelist**, karena data harga bersifat kritikal dan tidak boleh tercampur antara versi lama dan baru.

## Kenapa Ini Penting?

Tanpa versioning, jika ada dua file harga dengan isi berbeda tapi sama-sama "aktif", chatbot bisa menjawab pakai harga yang salah/kadaluarsa. Dengan versioning, hanya **satu versi aktif** yang dipakai chatbot, versi lama tetap tersimpan untuk keperluan audit atau referensi.

## Cara Kerja (Sederhana)

```
Upload Pricelist baru
        │
        ▼
Sistem cek: apakah ada file dengan nama sama (dan replace=true)?
        │
        ├── Ya  → Versi lama diarsipkan otomatis
        │
        └── Tidak → Sistem cek: apakah ada versi Pricelist lain yang masih aktif?
                        │
                        ├── Ada satu → Otomatis dijadikan versi lama (superseded)
                        │
                        └── Ada lebih dari satu → Upload ditolak, admin harus
                            pilih manual file mana yang digantikan
```

## Dua Cara Upload Versi Baru

### Cara 1 — Nama File Sama

Contoh: upload ulang `pricelist_dell.xlsx` **dengan opsi Ganti jika sudah ada** (`replace=true`) untuk menggantikan `pricelist_dell.xlsx` yang lama. Tanpa opsi ini upload ditolak (409).

**Yang terjadi otomatis:**
- File lama dipindahkan ke folder arsip (`_archive/`), bukan dihapus.
- File baru menempati nama yang sama seperti sebelumnya.
- Admin perlu klik **Ingest**, lalu **Approve** agar versi baru dipakai chatbot.
- Selama belum di-Ingest dan di-Approve, **chatbot tidak menjawab dari pricelist ini**: row status asli dihapus, sehingga chunk lama tidak lolos filter `hybrid_search` (wajib `approved` + `active`). Row status lama dipindahkan ke `_archive_...`; chunk di `documents` baru ditimpa saat Ingest.

### Cara 2 — Nama File Berbeda

Contoh: upload `pricelist_dell_2027.xlsx` untuk menggantikan `pricelist_dell_2026.xlsx`.

**Yang terjadi otomatis:**
- Jika hanya ada **satu** versi Pricelist yang sedang aktif, sistem otomatis menandainya sebagai "digantikan" (superseded).
- Jika ada **lebih dari satu** versi aktif, admin harus memberi tahu sistem secara eksplisit file mana yang digantikan.

Admin dapat menyebut file lama lewat parameter `supersedes` pada API, atau kolom **Supersedes filename** pada dialog upload Dashboard.

Jika upload ter-flag (duplicate/confidential), versi lama **tetap** sudah di-supersede dan vector-nya dihapus walau versi baru belum bisa di-ingest.

## Status Dokumen di Dashboard

| Status | Artinya |
|---|---|
| **Sudah ingest** | Dokumen ini aktif dan dipakai chatbot untuk menjawab pertanyaan. |
| **Belum ingest** | Dokumen sudah diupload tapi belum diaktifkan — perlu klik **Ingest**. |
| **Superseded** | Dokumen ini adalah versi lama yang sudah digantikan. Tidak dipakai chatbot lagi, tapi tetap tersimpan untuk arsip. |
| **Arsip** | File hasil pemindahan otomatis dari proses replace (Cara 1). Row statusnya bernama `{category}:_archive_{timestamp}_{nama}`, otomatis `superseded`, dan dilewati oleh Sync. Tidak seharusnya di-ingest; Dashboard dan endpoint `/ingest` belum memblokirnya. |

## Yang Perlu Diingat Admin

1. **File arsip tidak boleh dihapus sembarangan** — ini adalah jejak historis harga yang pernah berlaku.
2. **Setelah upload versi baru, klik Ingest lalu Approve** — upload saja tidak mengaktifkan dokumen ke chatbot (`approval_status` kembali `pending`).
3. **Jika sistem menolak upload karena "banyak versi aktif ditemukan"** — hubungi tim teknis untuk bantuan menentukan versi mana yang seharusnya digantikan.
4. Fitur ini saat ini **hanya berlaku untuk kategori Pricelist**. Kategori lain (SOP, Datasheet, dll.) belum menggunakan sistem versioning ini.
5. **Pada Cara 1, pricelist tidak dijawab chatbot sampai versi baru di-Ingest dan di-Approve.** Segera lakukan keduanya setelah upload.

## Tanggal Efektif & Nomor Versi

- Metadata `version` = jumlah dokumen yang pernah digantikan oleh `document_id` ini + 1.
- "Tanggal efektif" yang disebut chatbot diambil dengan prioritas: `effective_date` (metadata yang diisi admin) → `updated_at` (waktu modifikasi file di MinIO) → `uploaded_at` (waktu ingest, tanpa timezone). Hanya 10 karakter pertama (tanggal) yang ditampilkan.
- Untuk Pricelist, isi `effective_date` saat upload agar tanggal yang disebut chatbot adalah tanggal berlaku harga yang sebenarnya.
