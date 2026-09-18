# Data Retention Policy — Session, Interaction & Feedback

## 1. Objective

Kebijakan ini mengatur periode penyimpanan, penggunaan, akses, dan penghapusan data yang dihasilkan oleh chatbot, termasuk:

* Session data.
* Interaction logs (query, jawaban, dan dokumen yang dirujuk).
* Response feedback (thumbs up/down beserta alasan).

Tujuan kebijakan ini adalah memastikan data hanya disimpan selama diperlukan untuk kebutuhan operasional, analytics, monitoring kualitas jawaban, audit, dan compliance.

---

## 2. Data Classification

| Data              | Storage                     | Isi Data                                                              |                                            Retention |
| ----------------- | ---------------------------- | ----------------------------------------------------------------------- | ----------------------------------------------------: |
| Session           | Session store                 | session ID, conversation history, timestamps                            |                                           Maks. 24 jam |
| Interaction logs  | `public.interaction_logs`     | anonymized query, jawaban, dokumen yang dirujuk (sources), anon ID, timestamp | 30 hari (tanpa feedback) / 90 hari (dengan feedback) |
| Response feedback | `public.response_feedback`    | rating (up/down), alasan opsional, request ID, timestamp                | Mengikuti retensi `interaction_logs` terkait (maks. 90 hari) |
| Application logs  | File/application logging      | technical logs dan performance metrics                                  |                            Sesuai log rotation policy |

Retention dihitung berdasarkan timestamp data dan menggunakan waktu UTC pada database.

---

# 3. Session Retention Policy

## 3.1 Session Identifier

Setiap session menggunakan unique session ID.

Session ID tidak boleh digunakan sebagai pengganti authentication credential dan tidak boleh mengandung informasi pribadi user.

## 3.2 Idle Timeout

Session memiliki idle timeout maksimal:

**30 menit**

Jika tidak terdapat aktivitas selama 30 menit, session dianggap expired.

## 3.3 Absolute Timeout

Session memiliki absolute timeout maksimal:

**24 jam**

Session harus dianggap expired setelah 24 jam sejak session dibuat, walaupun terdapat aktivitas selama periode tersebut.

## 3.4 Conversation History

Conversation history hanya disimpan selama session masih aktif.

Setelah session expired, conversation history harus dihapus dari session store dan tidak boleh dipertahankan tanpa kebutuhan bisnis yang sah.

## 3.5 Session Storage

Environment development dapat menggunakan in-memory session store.

Production harus menggunakan persistent session store yang mendukung expiration/TTL, seperti database atau Redis.

Session store production harus menerapkan:

```text
Idle timeout    : 30 minutes
Absolute timeout: 24 hours
```

## 3.6 Session Deletion

Expired session harus dihapus secara otomatis oleh session store atau scheduled cleanup mechanism.

Sistem tidak boleh bergantung pada aktivitas user berikutnya untuk mempertahankan data session yang sudah expired.

---

# 4. Interaction Log Retention

## 4.1 Stored Data

System menyimpan data berikut pada `public.interaction_logs`:

* `id` — unique identifier.
* `request_id` — identifier request, digunakan untuk menghubungkan ke `response_feedback`.
* `session_id` — identifier session terkait.
* `query` — query user yang telah melalui anonymization.
* `answer` — jawaban chatbot untuk request tersebut.
* `sources` — metadata dokumen/chunk yang dirujuk untuk menghasilkan jawaban (document_id, category, section_title, dll).
* `fallback` — penanda apakah jawaban merupakan fallback (tidak ditemukan informasi relevan).
* `timestamp` — waktu query diterima.
* `anon_id` — anonymous identifier.

Data pribadi seperti nama, email, dan nomor telepon tidak boleh disimpan dalam bentuk raw pada `query` maupun `answer`.

## 4.2 Retention Period — Bertingkat

Retention `interaction_logs` mengikuti dua tingkat, tergantung apakah baris tersebut memiliki feedback terkait pada `response_feedback`:

| Kondisi                                             | Retention |
| ---------------------------------------------------- | --------: |
| Tidak memiliki feedback terkait                      |   30 hari |
| Memiliki minimal satu feedback terkait (up/down)     |   90 hari |

Alasan retensi bertingkat:

* Baris tanpa feedback tidak memiliki nilai analitik tambahan setelah 30 hari, sehingga tetap mengikuti prinsip minimisasi data.
* Baris dengan feedback dibutuhkan lebih lama untuk mendukung analisis tren kualitas jawaban dan identifikasi dokumen bermasalah (lihat [Analytics Endpoints](#12-relasi-dengan-analytics) pada bagian selanjutnya), yang memerlukan horizon waktu lebih dari 30 hari agar keputusan revisi dokumen tidak terpotong prematur oleh penghapusan data.

Setelah melewati periode retensi yang berlaku, baris harus dihapus secara otomatis.

Contoh:

```text
Interaction tanpa feedback
Timestamp  : 1 September 2026 10:00 UTC
Retention  : 30 hari
Eligible delete : 1 Oktober 2026 10:00 UTC

Interaction dengan feedback
Timestamp  : 1 September 2026 10:00 UTC
Retention  : 90 hari
Eligible delete : 30 November 2026 10:00 UTC
```

Jika feedback baru masuk untuk suatu interaction setelah baris tersebut sudah lebih dari 30 hari namun belum mencapai 90 hari, baris tersebut otomatis tidak lagi memenuhi kriteria penghapusan pada siklus cleanup berikutnya (retensi mengikuti kondisi baris pada saat cleanup dijalankan).

## 4.3 Purpose Limitation

Interaction log hanya digunakan untuk:

* Analytics penggunaan chatbot.
* Identifikasi top FAQ.
* Identifikasi potential content gaps.
* Monitoring kualitas chatbot dan jawaban bermasalah.
* Identifikasi dokumen yang memerlukan revisi berdasarkan feedback negatif.
* Reporting penggunaan chatbot.

Interaction log tidak boleh digunakan untuk tujuan lain tanpa review dan approval yang sesuai.

---

# 5. Query & Answer Privacy & Anonymization

Sebelum disimpan ke `interaction_logs`, query harus melalui proses anonymization.

Contoh data yang harus direduksi:

```text
Email → [EMAIL]
Phone → [PHONE]
Nama  → [NAME]
```

Raw query tidak boleh ditulis ke database interaction log.

Anonymization harus dilakukan sebelum fungsi logging dipanggil.

Application log juga tidak boleh mencatat raw query apabila query tersebut dapat mengandung PII.

Mekanisme anonymization harus direview secara berkala karena pattern-based anonymization tidak menjamin seluruh kemungkinan PII dapat terdeteksi.

Jawaban chatbot (`answer`) dihasilkan dari knowledge base internal dan tidak diharapkan memuat PII pengguna, namun tetap tunduk pada retensi bertingkat yang sama dengan baris `interaction_logs` yang menyimpannya.

---

# 6. Response Feedback Retention

## 6.1 Stored Data

`public.response_feedback` menyimpan:

* `id` — unique identifier.
* `request_id` — mengacu ke `interaction_logs.request_id`.
* `rating` — `up` atau `down`.
* `reason` — alasan opsional, khususnya untuk feedback negatif.
* `created_at`.

## 6.2 Retention Period

Response feedback **tidak memiliki periode retensi independen**. Baris ini dihapus secara otomatis mengikuti retensi baris `interaction_logs` yang menjadi induknya (relasi `on delete cascade`), yaitu:

**Maksimal 90 hari**, mengikuti tingkat retensi `interaction_logs` yang memiliki feedback (lihat [4.2](#42-retention-period--bertingkat)).

Dengan kata lain, response feedback tidak akan pernah bertahan lebih lama dibanding interaction log yang direferensikannya, dan akan ikut terhapus begitu interaction log tersebut dihapus oleh scheduled cleanup.

## 6.3 Purpose Limitation

Response feedback digunakan untuk:

* Mengukur tingkat kepuasan terhadap jawaban chatbot.
* Mengidentifikasi jawaban bermasalah (downvote tinggi).
* Mengidentifikasi dokumen/chunk yang berkontribusi terhadap jawaban bermasalah.

---

# 7. Automatic Deletion

System harus menyediakan scheduled cleanup job untuk menghapus data yang telah melewati retention period.

Kriteria deletion:

```sql
-- Interaction logs tanpa feedback: 30 hari
-- Interaction logs dengan feedback: 90 hari
-- (response_feedback ikut terhapus otomatis via on delete cascade)
```

Contoh SQL:

```sql
delete from public.interaction_logs i
where (
    not exists (
        select 1 from public.response_feedback f
        where f.request_id = i.request_id
    )
    and i.timestamp < now() - interval '30 days'
)
or (
    exists (
        select 1 from public.response_feedback f
        where f.request_id = i.request_id
    )
    and i.timestamp < now() - interval '90 days'
);
```

Penghapusan `interaction_logs` yang memiliki feedback akan otomatis menghapus baris `response_feedback` terkait melalui foreign key `on delete cascade`, sehingga tidak diperlukan statement DELETE terpisah untuk `response_feedback`.

Deletion harus dilakukan oleh service account yang memiliki permission yang sesuai.

Scheduled cleanup harus dijalankan secara berkala, minimal sekali dalam sehari.

---

# 8. Session Cleanup

Session cleanup mengikuti expiration policy:

```text
Idle timeout     : 30 minutes
Absolute timeout : 24 hours
```

Session yang memenuhi salah satu kondisi berikut harus dianggap expired:

```text
now - last_activity >= 30 minutes
```

atau:

```text
now - created_at >= 24 hours
```

Expired session dan conversation history terkait harus dihapus dari session store.

---

# 9. Relasi dengan Analytics

Retensi bertingkat pada `interaction_logs` dan `response_feedback` secara langsung mendukung dua kebutuhan analytics berikut:

* **Identifikasi jawaban bermasalah** — memerlukan `interaction_logs.answer` dan `interaction_logs.sources` tetap tersedia selama periode retensi yang berlaku agar dapat dikorelasikan dengan `response_feedback.rating` dan `response_feedback.reason`.
* **Identifikasi dokumen/chunk yang perlu direvisi** — memerlukan `interaction_logs.sources` yang memuat metadata dokumen (document_id, category) tetap tersedia untuk periode yang cukup panjang agar tren downvote per dokumen dapat diamati.

Jika horizon retensi 90 hari dianggap tidak cukup untuk kebutuhan bisnis di masa depan, perubahan periode ini harus melalui review kebijakan (lihat [Policy Review](#14-policy-review)), bukan diubah secara ad-hoc pada kode aplikasi.

---

# 10. Access Control

Akses terhadap retention data harus mengikuti principle of least privilege.

### Interaction Logs & Response Feedback

Akses analytics/export (termasuk endpoint identifikasi jawaban bermasalah dan dokumen yang perlu direvisi) dibatasi kepada role yang memiliki kebutuhan bisnis yang sah, khususnya `Admin`.

### Session Data

Session data hanya boleh diakses oleh application backend dan komponen yang membutuhkan session tersebut.

---

# 11. Export

Data hasil export yang berasal dari interaction log harus mengikuti retention dan access-control policy.

File export:

* Tidak boleh disimpan lebih lama dari kebutuhan bisnis.
* Harus diperlakukan sebagai restricted/internal data.
* Tidak boleh dipublikasikan.
* Harus dihapus setelah kebutuhan reporting selesai.

Jika export mengandung query atau jawaban user, anonymization policy tetap berlaku.

---

# 12. Failure Handling

Kegagalan logging tidak boleh menyebabkan request chatbot gagal.

Contoh:

```text
Chat request      → tetap diproses
Interaction logging → tetap dilakukan secara synchronous sebelum retrieval,
                       namun kegagalan tidak menghentikan request
Answer update      → asynchronous, kegagalan tidak menghentikan response ke user
Feedback logging   → synchronous terhadap request feedback, namun tidak
                       memengaruhi proses chat yang sudah selesai
Logging failure    → dicatat sebagai application error
```

Namun, kegagalan scheduled deletion harus dimonitor dan menghasilkan operational alert agar retention requirement tetap dapat dipenuhi.

---

# 13. Audit & Compliance Verification

Implementasi retention harus dapat diverifikasi melalui:

### Session

* Review idle timeout.
* Review absolute timeout.
* Test expired session.
* Test conversation history deletion.

### Interaction Logs

* Test interaction log tanpa feedback lebih dari 30 hari terhapus.
* Test interaction log dengan feedback tetap tersimpan hingga 90 hari.
* Test interaction log dengan feedback lebih dari 90 hari terhapus.
* Test anonymization sebelum insert.
* Review access control.
* Review export authorization.

### Response Feedback

* Test response feedback terhapus otomatis mengikuti penghapusan interaction log induknya (cascade).
* Review access control terhadap endpoint analytics feedback.

### Scheduled Cleanup

* Review cleanup execution log.
* Review failed cleanup events.
* Verify database records after cleanup, termasuk verifikasi bahwa baris berfeedback tidak terhapus prematur sebelum 90 hari.

---

# 14. Retention Summary

```text
Session idle timeout      : 30 minutes
Session absolute timeout  : 24 hours

Interaction logs (tanpa feedback) : 30 days
Interaction logs (dengan feedback): 90 days
Response feedback                 : mengikuti interaction log induk (maks. 90 days)
```

Retention period dihitung dari timestamp masing-masing record dan menggunakan UTC sebagai basis waktu database.

---

# 15. Policy Review

Retention policy harus direview apabila terdapat perubahan pada:

* PRD atau business requirement.
* Analytics requirement.
* Privacy requirement.
* Compliance requirement.
* Struktur database.
* Session management architecture.
* Logging architecture.
* Storage provider.
* Export requirement.

Review juga harus dilakukan apabila terdapat kebutuhan untuk memperpanjang retention period, termasuk perubahan ambang 90 hari pada interaction log berfeedback apabila kebutuhan analisis tren jawaban bermasalah berubah.

**Current retention policy:**

```text
Session:
30 minutes idle / 24 hours absolute

Interaction logs:
30 days (tanpa feedback) / 90 days (dengan feedback)

Response feedback:
Mengikuti interaction log induk (maks. 90 days)
```