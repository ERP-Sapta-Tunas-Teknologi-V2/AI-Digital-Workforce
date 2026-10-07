# Audit Knowledge Expert untuk Sales Copilot

## 1. Tujuan

Melakukan audit terhadap RAG pipeline yang digunakan oleh Knowledge Expert untuk menentukan apakah pipeline tersebut dapat digunakan kembali sebagai fondasi **Sales Copilot** tanpa membuat pipeline RAG baru.

Audit mencakup:

- Pipeline ingestion dokumen
- Cleaning dan parsing dokumen
- Chunking dan metadata
- Hybrid retrieval
- RBAC pada retrieval
- Citation metadata
- Akses ke dokumen sumber
- Injection scanning

## 2. Ruang Lingkup

File yang diaudit:

- `ingestion/loader.py`
- `ingestion/cleaner.py`
- `ingestion/indexer.py`
- `ingestion/splitter.py`
- `utils/injection_patterns.py`
- `utils/permissions.py`
- `routes/chat.py`
- `rag/retriever.py`
- `supabase.sql`

`static/chat.js` tidak diaudit karena sudah tidak digunakan oleh frontend saat ini.

## 3. Kesimpulan

**VERDICT: CONDITIONAL REUSE**

Arsitektur RAG Knowledge Expert dapat digunakan kembali sebagai fondasi Sales Copilot.

Tidak diperlukan pipeline ingestion atau retrieval khusus untuk Sales.

Namun, terdapat beberapa gap yang harus diperbaiki atau divalidasi sebelum Sales Copilot digunakan untuk production.

## 4. Hasil Audit

| Area | Status | Temuan |
|---|---|---|
| PDF ingestion | PASS | Pipeline preprocessing dan loading PDF dapat digunakan kembali. |
| DOCX ingestion | PASS | DOCX dikonversi ke PDF kemudian diproses melalui pipeline yang sudah ada. |
| XLSX ingestion | PASS | XLSX didukung melalui Docling dan `split_docling()`. |
| PPTX ingestion | GAP | Parser saat ini terutama mengambil `shape.text`; tabel, grouped shapes, notes, gambar, dan konten terstruktur lainnya dapat terlewat. |
| Table chunking | PASS | Tabel berukuran besar dapat dipecah menjadi beberapa chunk dengan header tabel tetap dipertahankan. |
| Page metadata | PASS | Informasi halaman disimpan dalam metadata chunk. |
| Section metadata | PASS | Judul section disimpan dalam metadata chunk. |
| Citation mechanism | PASS | Retrieved document membawa source, page, category, section, version, dan citation metadata. |
| Citation date | GAP | `uploaded_at` dibuat saat proses indexing sehingga menunjukkan waktu ingestion, bukan waktu efektif/update dokumen. |
| Image content | GAP | Picture block tidak dimasukkan ke chunk dan image-to-text saat ini tidak aktif. |
| Injection scanning | NEEDS VALIDATION | Beberapa pattern dapat cocok dengan bahasa Sales yang legitimate seperti `act as`, `pretend`, atau `answer exactly`. |
| Sales categories | PASS | Kategori `pricelist`, `case`, `proposal`, `competitive`, dan `datasheet` sudah tersedia. |
| RBAC configuration | PASS | `CATEGORY_ACCESS` sudah mendefinisikan akses kategori untuk role Sales dan Solution Architect. |
| RBAC SQL filtering | PASS | `hybrid_search()` menerapkan `category_filter` pada full-text dan semantic retrieval. |
| RBAC Python integration | GAP | `role` diteruskan ke `hybrid_retrieve()`, tetapi `get_allowed_categories(role)` belum dipanggil. |
| Source download authorization | NEEDS REVIEW | Endpoint `/sources/download` belum terlihat menerapkan authorization berdasarkan role/category. |

## 5. Gap yang Telah Dikonfirmasi

### G-01 — Ekstraksi PPTX masih terbatas

`pptx_to_md()` saat ini terutama mengambil `shape.text`.

Konten yang berpotensi tidak terambil atau tidak lengkap:

- Tabel
- Grouped shapes
- Speaker notes
- Gambar
- Chart
- Diagram

**Dampak:**

Informasi dari dokumen seperti competitive intelligence, case study, atau presentasi Sales dapat hilang saat proses ingestion.

**Rekomendasi:** T0.4

**Estimasi effort:** Medium

---

### G-02 — Konten gambar tidak di-index

Proses image-to-text pada `cleaner.py` saat ini tidak aktif dan `picture` block dibuang oleh chunker.

**Dampak:**

Informasi yang hanya terdapat di dalam diagram, screenshot, chart, atau gambar tidak dapat ditemukan melalui retrieval.

**Rekomendasi:** T0.4

**Estimasi effort:** Medium

---

### G-03 — Tanggal citation merupakan waktu ingestion

Pada `indexer.py`, nilai berikut dibuat ketika dokumen di-index:

```python
uploaded_at = datetime.now()
```

Nilai tersebut kemudian disimpan sebagai metadata dan digunakan pada context retrieval sebagai:

```text
tanggal efektif
```

Dengan demikian, tanggal yang ditampilkan sebenarnya merupakan **waktu ingestion**, bukan tanggal efektif atau tanggal terakhir dokumen diperbarui.

**Dampak:**

User dapat menganggap tanggal ingestion sebagai tanggal efektif/update dokumen.

**Rekomendasi:** T0.6

**Estimasi effort:** Small/Medium

---

### G-04 — RBAC belum diterapkan pada Python retrieval path

Konfigurasi RBAC sudah tersedia dan SQL `hybrid_search()` sudah mendukung filtering berdasarkan kategori.

Namun, `routes/chat.py` saat ini memanggil:

```python
hybrid_retrieve(contextual_question, request_id, role)
```

tanpa mengirimkan:

```python
get_allowed_categories(role)
```

Akibatnya parameter `allowed_categories` pada `hybrid_retrieve()` tetap bernilai `None`.

SQL kemudian menerima:

```text
category_filter = NULL
```

sehingga filtering kategori tidak diterapkan.

**Dampak:**

Pembatasan dokumen berdasarkan role belum diterapkan pada retrieval path saat ini.

**Severity:** High

**Rekomendasi:** Perbaiki sebelum Sales Copilot digunakan untuk production.

**Estimasi effort:** Small

---

## 6. Temuan yang Membutuhkan Validasi

### G-05 — Injection pattern berpotensi menghasilkan false positive

Pipeline ingestion menerapkan injection pattern terhadap isi dokumen.

Beberapa pattern memang sesuai untuk mendeteksi prompt injection, tetapi pattern seperti:

```text
act as
pretend
answer exactly
when asked ... answer
```

dapat muncul secara legitimate di dokumen Sales.

Contoh:

```text
Act as a trusted advisor for enterprise customers.
```

atau:

```text
When asked about pricing, answer exactly based on the approved pricelist.
```

Konten tersebut berpotensi terkena `[REDACTED]`.

**Validasi yang diperlukan:**

Test terhadap dokumen Sales nyata:

- Datasheet
- Pricelist
- Competitive intelligence
- Case study
- Proposal template

Jika konten legitimate terkena redaction, strategi injection scanning perlu disesuaikan.

**Rekomendasi:** T0.4

---

### G-06 — Authorization pada source download perlu diperiksa

Endpoint:

```text
/sources/download
```

sudah melakukan sanitasi filename untuk mencegah path traversal.

Namun, route tersebut tidak terlihat menerapkan pengecekan role/category seperti retrieval.

Authorization perlu diverifikasi untuk memastikan user tidak dapat mengunduh dokumen di luar akses RBAC-nya.

**Rekomendasi:** Security follow-up sebelum production.

---

## 7. Komponen yang Dapat Digunakan Kembali

Komponen Knowledge Expert berikut dapat digunakan sebagai fondasi Sales Copilot:

```text
Knowledge Expert
├── Document ingestion
├── Document cleaning
├── Docling loading
├── Structure-aware chunking
├── Embedding pipeline
├── Supabase pgvector storage
├── Hybrid search
├── Reranking
├── Category-based RBAC model
├── Citation metadata
└── Retrieval context generation
```

Tidak diperlukan pembuatan RAG pipeline khusus untuk Sales.

## 8. Kategori Dokumen Sales

Kategori yang dibutuhkan untuk scope awal Sales Copilot sudah tersedia:

```text
pricelist
datasheet
competitive
case
proposal
```

Tidak diperlukan penambahan kategori baru untuk tahap awal.

## 9. Rekomendasi

Gunakan Knowledge Expert sebagai fondasi Sales Copilot.

Prioritas perbaikan:

1. Hubungkan `role` dengan `get_allowed_categories()` pada retrieval path.
2. Pastikan authorization pada source download mengikuti RBAC.
3. Validasi dan tingkatkan ekstraksi PPTX.
4. Validasi injection scanning menggunakan dokumen Sales nyata.
5. Gunakan tanggal efektif/update dokumen yang sebenarnya untuk citation, bukan timestamp ingestion.

## 10. Kriteria Penyelesaian T0.1

T0.1 dinyatakan selesai apabila:

- [x] Pipeline ingestion telah diaudit.
- [x] Konfigurasi RBAC telah diaudit.
- [x] Retrieval filtering telah diaudit.
- [x] Citation metadata telah diaudit.
- [x] Komponen yang dapat digunakan kembali telah diidentifikasi.
- [x] Gap telah didokumentasikan.
- [x] Pertanyaan evaluasi Sales telah dibuat.
- [x] Verdict reuse telah ditentukan.

### Final Verdict

**CONDITIONAL REUSE**

Knowledge Expert dapat digunakan kembali sebagai fondasi Sales Copilot. Tidak diperlukan pembuatan pipeline RAG baru, tetapi gap RBAC dan beberapa keterbatasan ingestion/citation harus ditangani sebelum digunakan untuk production.