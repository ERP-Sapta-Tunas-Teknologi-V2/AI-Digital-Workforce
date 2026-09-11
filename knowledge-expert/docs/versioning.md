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
Sistem cek: apakah ada file dengan nama sama?
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

Contoh: upload ulang `pricelist_dell.xlsx` untuk menggantikan `pricelist_dell.xlsx` yang lama.

**Yang terjadi otomatis:**
- File lama dipindahkan ke folder arsip (`_archive/`), bukan dihapus.
- File baru menempati nama yang sama seperti sebelumnya.
- Admin perlu klik tombol **Ingest** untuk mengaktifkan versi baru ke chatbot.

### Cara 2 — Nama File Berbeda

Contoh: upload `pricelist_dell_2027.xlsx` untuk menggantikan `pricelist_dell_2026.xlsx`.

**Yang terjadi otomatis:**
- Jika hanya ada **satu** versi Pricelist yang sedang aktif, sistem otomatis menandainya sebagai "digantikan" (superseded).
- Jika ada **lebih dari satu** versi aktif, admin harus memberi tahu sistem secara eksplisit file mana yang digantikan.

## Status Dokumen di Dashboard

| Status | Artinya |
|---|---|
| **Sudah ingest** | Dokumen ini aktif dan dipakai chatbot untuk menjawab pertanyaan. |
| **Belum ingest** | Dokumen sudah diupload tapi belum diaktifkan — perlu klik **Ingest**. |
| **Superseded** | Dokumen ini adalah versi lama yang sudah digantikan. Tidak dipakai chatbot lagi, tapi tetap tersimpan untuk arsip. |
| **Arsip** | File hasil pemindahan otomatis dari proses replace (Cara 1). Tidak bisa di-ingest ulang secara terpisah. |

## Yang Perlu Diingat Admin

1. **File arsip tidak boleh dihapus sembarangan** — ini adalah jejak historis harga yang pernah berlaku.
2. **Setelah upload versi baru, jangan lupa klik Ingest** — upload saja tidak otomatis mengaktifkan dokumen ke chatbot.
3. **Jika sistem menolak upload karena "banyak versi aktif ditemukan"** — hubungi tim teknis untuk bantuan menentukan versi mana yang seharusnya digantikan.
4. Fitur ini saat ini **hanya berlaku untuk kategori Pricelist**. Kategori lain (SOP, Datasheet, dll.) belum menggunakan sistem versioning ini.