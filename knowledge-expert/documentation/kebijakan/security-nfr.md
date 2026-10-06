# Encryption at Rest & TLS in Transit

Arsitektur Knowledge Expert mendukung encryption at rest dan TLS in transit sesuai NFR keamanan data.

## Encryption at rest

* Supabase menyediakan encryption at rest untuk database dan storage.
* MinIO digunakan sebagai document storage dan pada production deployment wajib dikonfigurasi dengan server-side encryption menggunakan KMS.
* Data dan temporary processing files tidak disimpan secara permanen di local filesystem aplikasi.

## TLS in transit

* Client → API menggunakan HTTPS pada production.
* API → Supabase menggunakan HTTPS/TLS.
* API → MinIO menggunakan TLS pada production apabila komunikasi melalui network.
* API → Ollama menggunakan TLS apabila service dipisahkan ke host/network lain.

## Development environment

* Flask, MinIO, dan Ollama berjalan pada host yang sama.
* Komunikasi Flask → MinIO dan Flask → Ollama menggunakan `localhost` sehingga traffic tidak melewati network eksternal.
* TLS untuk koneksi localhost tidak diaktifkan pada development environment.

## Production requirement

* MinIO harus menggunakan encryption at rest dengan KMS/SSE.
* Endpoint MinIO yang diakses melalui network harus menggunakan TLS.
* Credential dan encryption key disimpan melalui secret management/environment configuration dan tidak disimpan di source code atau repository.

## HTTP Security Headers

Diset pada setiap response (`app.py`):

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## Konfigurasi TLS MinIO

TLS ke MinIO diaktifkan dengan `MINIO_SECURE=true` (default `false`, hanya untuk development). `MINIO_SECURE=true` wajib di production.

## Catatan Tambahan

* Redis (lock dan rate limit) berjalan di `localhost` tanpa TLS. Isinya hanya counter IP dan lock key.
* `ensure_bucket()` tidak mengaktifkan SSE, sehingga enkripsi KMS harus dikonfigurasi di MinIO (lihat dokumentasi MinIO KMS/KES).
* Risiko: tabel `documents` memberi akses penuh ke role `anon` dan `vectorstore.py` memakai publishable key. Rekomendasi: pindah ke `supabase_admin` dan cabut policy tulis `anon`.
* `/api/sources/download` bersifat publik dan tidak melewati RBAC kategori.
