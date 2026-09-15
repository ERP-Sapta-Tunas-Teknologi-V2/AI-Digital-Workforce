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
