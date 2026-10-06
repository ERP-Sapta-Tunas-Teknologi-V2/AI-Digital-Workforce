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
- Admin perlu klik tombol **Ingest** untuk mengaktifkan versi baru ke chatbot.
- **Vector versi lama masih dipakai chatbot** sampai versi baru di-Ingest. Row status lama dipindahkan ke `_archive_...` dan row asli dihapus, tetapi chunk di `documents` belum diganti.

### Cara 2 — Nama File Berbeda

Contoh: upload `pricelist_dell_2027.xlsx` untuk menggantikan `pricelist_dell_2026.xlsx`.

**Yang terjadi otomatis:**
- Jika hanya ada **satu** versi Pricelist yang sedang aktif, sistem otomatis menandainya sebagai "digantikan" (superseded).
- Jika ada **lebih dari satu** versi aktif, admin harus memberi tahu sistem secara eksplisit file mana yang digantikan.

Via API, admin dapat menyebut file lama lewat parameter `supersedes`. Dashboard belum mendukung ini.

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
2. **Setelah upload versi baru, jangan lupa klik Ingest** — upload saja tidak otomatis mengaktifkan dokumen ke chatbot.
3. **Jika sistem menolak upload karena "banyak versi aktif ditemukan"** — hubungi tim teknis untuk bantuan menentukan versi mana yang seharusnya digantikan.
4. Fitur ini saat ini **hanya berlaku untuk kategori Pricelist**. Kategori lain (SOP, Datasheet, dll.) belum menggunakan sistem versioning ini.
5. **Pada Cara 1, vector versi lama masih dipakai chatbot sampai versi baru di-Ingest.** Segera klik Ingest setelah upload.

## Tanggal Efektif & Nomor Versi

- Metadata `version` = jumlah dokumen yang pernah digantikan oleh `document_id` ini + 1.
- "Tanggal efektif" yang disebut chatbot adalah **waktu ingest** (`uploaded_at` = `datetime.now()` server saat indexing, tanpa timezone), bukan tanggal berlaku harga pada dokumen.
