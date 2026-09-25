# RBAC Policy

## 1. Objective

Kebijakan ini mengatur akses berbasis role terhadap dua area berbeda pada sistem:

1. **Akses endpoint** — endpoint admin dan analytics yang dibatasi untuk role tertentu.
2. **Akses konten (retrieval filtering)** — kategori dokumen yang boleh diambil (retrieve) sebagai konteks jawaban chatbot, berdasarkan role/departemen pengguna.

Kedua area ini independen. Role yang punya akses endpoint tertentu tidak otomatis punya akses kategori dokumen tertentu, dan sebaliknya.

---

## 2. Daftar Role

```text
Admin
Sales
Solution Architect
```

Role dikirim oleh client melalui header:

```http
X-User-Role: <role>
```

Tidak ada validasi identitas/login di balik header ini pada implementasi saat ini — lihat [Batasan & Risiko](#7-batasan--risiko).

---

## 3. Endpoint Access Control

Berlaku untuk endpoint yang menggunakan decorator `require_role`.

| Endpoint | Method | Role yang Diizinkan |
| --- | --- | --- |
| `/api/admin/documents/upload` | POST | Admin |
| `/api/admin/documents` | GET | Admin |
| `/api/admin/ingest` | POST | Admin |
| `/api/admin/un-ingest` | POST | Admin |
| `/api/admin/documents/delete` | DELETE | Admin |
| `/api/admin/documents/download` | GET | Admin |
| `/api/admin/sync` | POST | Admin |
| `/api/logs/export` | GET | Admin |
| `/api/logs/top-faq` | GET | Admin |
| `/api/chat` | POST | Public (tidak dibatasi role) |

### Response Tanpa Role

```json
{ "error": "authentication required" }
```

Status: `401 Unauthorized`

### Response Role Tidak Sesuai

```json
{ "error": "forbidden" }
```

Status: `403 Forbidden`

---

## 4. Content Access Control (Retrieval Filtering)

Membatasi kategori dokumen yang boleh digunakan sebagai konteks retrieval berdasarkan role/departemen, sebelum konteks dikirim ke LLM.

### 4.1 Matrix Akses Kategori

| Kategori | Role yang Diizinkan |
| --- | --- |
| General | Semua role |
| SOP | Semua role |
| Pricelist | Sales |
| Case Study | Semua role |
| Meeting Notes | Sales |
| Training Material | Semua role |
| Solution Architecture | Solution Architect |
| Proposal Template | Semua role |
| Technical Guide | Solution Architect |
| Competitive | Semua role |
| Datasheet | Sales, Solution Architect |
| SoW | Semua role |

### 4.2 Perilaku Default (Tanpa Header Role)

| Kondisi | Kategori yang Diizinkan |
| --- | --- |
| Header `X-User-Role` **tidak dikirim** | Tidak difilter — seluruh kategori diizinkan (perilaku legacy, dipakai widget chat publik) |
| Header `X-User-Role` **dikirim** dengan role dikenal | Sesuai matrix pada 4.1 |
| Header `X-User-Role` **dikirim** dengan role tidak dikenal | Hanya kategori dengan akses "Semua role" (SOP, Training Material) |

### 4.3 Titik Penerapan

Filter diterapkan pada level query database (`hybrid_search` RPC), bukan post-filtering setelah reranking. Dengan demikian, chunk dari kategori yang tidak diizinkan **tidak pernah masuk** ke tahap embedding-matching, reranking, maupun context yang dikirim ke LLM.

```text
Request (question + role)
        │
        ▼
Tentukan allowed_categories berdasarkan role
        │
        ▼
Hybrid Search (filter category di SQL)
        │
        ▼
Reranking (hanya dari kategori yang diizinkan)
        │
        ▼
Context → LLM
```

### 4.4 Contoh

**Role: Sales, pertanyaan tentang harga**

```text
allowed_categories = [sop, datasheet, pricelist, meeting, training]
→ chunk pricelist dapat digunakan sebagai konteks
```

**Role: Solution Architect, pertanyaan tentang harga**

```text
allowed_categories = [sop, guide, datasheet, training]
→ chunk pricelist TIDAK di-retrieve, meskipun relevan secara semantik
→ jika seluruh dokumen relevan berada di kategori pricelist,
  chatbot menjawab fallback: "Informasi tidak ditemukan dalam knowledge base."
```

**Tanpa header role (chat widget publik di `/`)**

```text
allowed_categories = None (tidak difilter)
→ seluruh kategori dapat diakses
```

---

## 5. Audit Logging

Setiap retrieval yang menerapkan filter RBAC (yaitu ketika `allowed_categories is not None`) dicatat untuk kebutuhan audit.

### 5.1 Lokasi Log

```text
log/log_rbac_audit.txt
```

### 5.2 Informasi yang Dicatat

| Field | Keterangan |
| --- | --- |
| `request_id` | ID unik request, untuk korelasi dengan log retrieval/LLM lainnya |
| `role` | Role yang mengirim request (`unknown` jika header ada tapi kosong) |
| `allowed_categories` | Daftar kategori yang diizinkan untuk role tersebut |
| `candidates_returned` / `blocked_chunks` | Jumlah chunk yang lolos filter, atau jumlah chunk yang ter-block (tergantung mode logging yang diaktifkan) |

Contoh entri log:

```text
[a1b2c3d4] RBAC_FILTER_APPLIED | role=Solution Architect | allowed_categories=['sop', 'guide', 'datasheet', 'training'] | candidates_returned=12
```

### 5.3 Tujuan Audit Log

* Membuktikan bahwa filter RBAC benar-benar diterapkan per request.
* Investigasi apabila ada laporan chatbot menjawab menggunakan informasi dari kategori yang seharusnya tidak boleh diakses oleh role tertentu.
* Analisis pola akses per role dari waktu ke waktu.

Log ini **tidak mencatat isi pertanyaan** secara default; jika dibutuhkan untuk investigasi mendalam, korelasikan `request_id` dengan `log/log_retrieval-docs.txt` yang sudah menyimpan pertanyaan (dalam bentuk anonymized).

---

## 6. Perbedaan dengan Kontrol Akses Lain

| Mekanisme | Fungsi | Menentukan Apa |
| --- | --- | --- |
| `require_role` (endpoint) | Authorization endpoint | Siapa yang boleh memanggil endpoint tertentu (admin, analytics) |
| RBAC retrieval filter | Content authorization | Kategori dokumen mana yang boleh menjadi konteks jawaban chatbot |
| CORS | Browser-level origin control | Domain mana yang boleh memanggil API dari browser |
| Rate limiting | Abuse prevention | Berapa banyak request per IP dalam periode waktu tertentu |

Keempatnya saling melengkapi dan tidak menggantikan satu sama lain. CORS dan rate limiting tidak dianggap sebagai authentication/authorization.

---

## 7. Batasan & Risiko

1. **Role tidak diverifikasi.** Header `X-User-Role` dapat dikirim oleh siapa saja tanpa proses login/token. Siapa pun yang tahu cara mengisi header dapat mengklaim role manapun. RBAC saat ini bersifat **kontrol akses berbasis klaim (claim-based)**, bukan kontrol akses yang terautentikasi penuh.
2. **Endpoint chat publik tanpa role = tanpa filter.** Karena tujuan desain saat ini adalah mendukung widget chat publik di `/` tanpa login, permintaan tanpa header `X-User-Role` **tidak difilter sama sekali** dan dapat mengakses seluruh kategori dokumen, termasuk Pricelist dan Meeting Notes. Ini adalah keputusan desain sementara, bukan default yang aman (secure-by-default) — perlu direview sebelum kategori sensitif baru ditambahkan.
3. **Decorator `require_role` di `admin.py` sedang non-aktif.** Endpoint admin (upload, ingest, delete, sync, dll.) saat ini dapat diakses tanpa role sampai decorator diaktifkan kembali di kode.
3. **Rekomendasi jangka panjang:** ganti header `X-User-Role` dengan token terautentikasi (misalnya JWT/session yang divalidasi backend) agar role tidak dapat dipalsukan oleh client, karena saat ini role hanya berbasis klaim tanpa verifikasi identitas.