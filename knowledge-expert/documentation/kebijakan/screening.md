# Mekanisme Pemeriksaan Dokumen

Setiap dokumen yang di-upload akan diperiksa terlebih dahulu sebelum di-ingest.

## 1. Dokumen diperiksa

Sistem melakukan pemeriksaan untuk mengetahui apakah dokumen:

* Merupakan duplikat dari dokumen yang sudah ada.
* Mengandung informasi yang bersifat rahasia atau terbatas.
* Mengandung tanda bahwa dokumen sudah tidak berlaku, seperti draft, deprecated, expired, atau kadaluarsa.

## 2. Dokumen tetap disimpan

Dokumen tetap di-upload dan disimpan meskipun ditemukan indikasi yang perlu diperiksa lebih lanjut.

## 3. Review diperlukan

Jika ditemukan **duplikat** atau **informasi rahasia**, akan muncul peringatan.

Admin perlu melakukan review terlebih dahulu untuk menentukan apakah dokumen tersebut boleh di-ingest.

## 4. Dokumen yang lolos pemeriksaan

Jika tidak ditemukan masalah yang memerlukan review, dokumen dapat di-ingest.

## Kesimpulan

**Upload → Pemeriksaan → Simpan → Review jika diperlukan → Ingest jika disetujui**

Tujuannya adalah mencegah dokumen duplikat atau dokumen yang berpotensi sensitif digunakan tanpa pemeriksaan.

## Detail Implementasi

| Flag           | Sumber deteksi                                                         | Memblokir ingest?      |
| -------------- | ---------------------------------------------------------------------- | ---------------------- |
| `duplicate`    | SHA-256 isi file sama dengan dokumen lain                              | Ya                     |
| `confidential` | Pola teks (mis. "confidential", "internal only", "rahasia perusahaan") | Ya                     |
| `stale`        | Pola teks (draft, deprecated, expired, kadaluarsa, tidak berlaku lagi) | Tidak (hanya ditandai) |
| `clean`        | Tidak ada temuan (hash tetap disimpan untuk deteksi duplikat)          | -                      |

* Screening berjalan saat **upload** dan **sync**. Endpoint `/ingest` hanya membaca flag yang sudah tersimpan.
* Pemindaian teks hanya untuk **.pdf dan .docx** (5.000 karakter pertama). `.xlsx` dan `.pptx` hanya diperiksa duplikat.
* `POST /api/admin/ingest` membalas `409` untuk dokumen `duplicate`/`confidential`, dan Sync melewatinya.
* Pesan error menyebut "endpoint override", tetapi endpoint tersebut **belum ada**. Saat ini dokumen yang diblokir harus diperbaiki lalu di-upload ulang (screening dijalankan ulang saat upload, flag lama dibersihkan) atau dokumen dihapus.