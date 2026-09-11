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