# Data Retention Policy — Session, Query & Usage Logs

## 1. Objective

Kebijakan ini mengatur periode penyimpanan, penggunaan, akses, dan penghapusan data yang dihasilkan oleh chatbot, termasuk:

* Session data.
* Query logs.
* Chat usage logs.
* Index usage logs.
* Budget alerts.

Tujuan kebijakan ini adalah memastikan data hanya disimpan selama diperlukan untuk kebutuhan operasional, analytics, monitoring, cost management, audit, dan compliance.

---

## 2. Data Classification

| Data             | Storage                   | Isi Data                                                 |                  Retention |
| ---------------- | ------------------------- | -------------------------------------------------------- | -------------------------: |
| Session          | Session store             | session ID, conversation history, timestamps             |               Maks. 24 jam |
| Query logs       | `public.query_logs`       | anonymized query, anon ID, timestamp                     |                    30 hari |
| Chat usage logs  | `public.chat_usage_logs`  | request ID, anon ID, token usage, model, cost, timestamp |                    90 hari |
| Index usage logs | `public.index_usage_logs` | embedding model, token usage, cost, timestamp            |                    90 hari |
| Budget alerts    | `public.budget_alerts`    | period, alert type, cost, budget, usage percentage       |                    90 hari |
| Application logs | File/application logging  | technical logs dan performance metrics                   | Sesuai log rotation policy |

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

# 4. Query Log Retention

## 4.1 Stored Data

System menyimpan data berikut pada `public.query_logs`:

* `id` — unique identifier.
* `query` — query user yang telah melalui anonymization.
* `timestamp` — waktu query diterima.
* `anon_id` — anonymous identifier.

Data pribadi seperti nama, email, dan nomor telepon tidak boleh disimpan dalam bentuk raw pada query log.

## 4.2 Retention Period

Query log disimpan selama maksimal:

**30 hari**

Setelah melewati periode tersebut, data harus dihapus secara otomatis.

Contoh:

```text
Query timestamp : 1 September 2026 10:00 UTC
Retention       : 30 days
Eligible delete : 1 October 2026 10:00 UTC
```

## 4.3 Purpose Limitation

Query log hanya digunakan untuk:

* Analytics penggunaan chatbot.
* Identifikasi top FAQ.
* Identifikasi potential content gaps.
* Monitoring kualitas chatbot.
* Reporting penggunaan chatbot.

Query log tidak boleh digunakan untuk tujuan lain tanpa review dan approval yang sesuai.

---

# 5. Query Privacy & Anonymization

Sebelum disimpan ke `query_logs`, query harus melalui proses anonymization.

Contoh data yang harus direduksi:

```text
Email → [EMAIL]
Phone → [PHONE]
Nama  → [NAME]
```

Raw query tidak boleh ditulis ke database query log.

Anonymization harus dilakukan sebelum fungsi logging dipanggil.

Application log juga tidak boleh mencatat raw query apabila query tersebut dapat mengandung PII.

Mekanisme anonymization harus direview secara berkala karena pattern-based anonymization tidak menjamin seluruh kemungkinan PII dapat terdeteksi.

---

# 6. Chat Usage Log Retention

## 6.1 Stored Data

`public.chat_usage_logs` menyimpan informasi penggunaan resource chatbot, antara lain:

* `request_id`
* `anon_id`
* embedding model
* embedding token usage
* embedding cost
* LLM model
* LLM input tokens
* LLM output tokens
* LLM input cost
* LLM output cost
* total tokens
* total cost
* `created_at`

Usage log tidak menyimpan isi pertanyaan atau jawaban chatbot.

## 6.2 Retention Period

Chat usage log disimpan selama maksimal:

**90 hari**

Retention ini digunakan untuk mendukung:

* Cost monitoring.
* Daily/weekly cost reporting.
* Budget monitoring.
* Usage analytics.
* Operational troubleshooting.
* Audit terhadap penggunaan model dan biaya.

Setelah 90 hari, data harus dihapus secara otomatis.

---

# 7. Index Usage Log Retention

## 7.1 Stored Data

`public.index_usage_logs` menyimpan:

* embedding model
* embedding tokens
* embedding cost
* `created_at`

Data digunakan untuk monitoring biaya dan penggunaan embedding pada proses indexing.

## 7.2 Retention Period

Index usage log disimpan selama maksimal:

**90 hari**

Setelah melewati retention period, data harus dihapus secara otomatis.

---

# 8. Budget Alert Retention

`public.budget_alerts` digunakan untuk mencatat event monitoring budget, termasuk:

* period type
* period date
* alert type
* cost
* budget
* usage percentage
* created timestamp

Budget alert disimpan selama maksimal:

**90 hari**

Data dapat digunakan untuk:

* Audit budget threshold.
* Investigasi cost anomaly.
* Monitoring historical budget status.

Setelah 90 hari, data harus dihapus secara otomatis.

---

# 9. Automatic Deletion

System harus menyediakan scheduled cleanup job untuk menghapus data yang telah melewati retention period.

Kriteria deletion:

```sql
-- Query logs
timestamp < now() - interval '30 days'

-- Usage logs
created_at < now() - interval '90 days'

-- Budget alerts
created_at < now() - interval '90 days'
```

Contoh SQL:

```sql
delete from public.query_logs
where timestamp < now() - interval '30 days';

delete from public.chat_usage_logs
where created_at < now() - interval '90 days';

delete from public.index_usage_logs
where created_at < now() - interval '90 days';

delete from public.budget_alerts
where created_at < now() - interval '90 days';
```

Deletion harus dilakukan oleh service account yang memiliki permission yang sesuai.

Scheduled cleanup harus dijalankan secara berkala, minimal sekali dalam sehari.

---

# 10. Session Cleanup

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

# 11. Access Control

Akses terhadap retention data harus mengikuti principle of least privilege.

### Query Logs

Akses analytics/export dibatasi kepada role yang memiliki kebutuhan bisnis yang sah, khususnya:

* Marketing
* Product

### Usage Logs

Usage dan cost data hanya dapat diakses oleh service role dan endpoint analytics yang telah diberi authorization.

Database table harus tidak dapat diakses langsung oleh anonymous atau authenticated client apabila tidak diperlukan.

### Session Data

Session data hanya boleh diakses oleh application backend dan komponen yang membutuhkan session tersebut.

---

# 12. Export

Data hasil export yang berasal dari query log atau usage log harus mengikuti retention dan access-control policy.

File export:

* Tidak boleh disimpan lebih lama dari kebutuhan bisnis.
* Harus diperlakukan sebagai restricted/internal data.
* Tidak boleh dipublikasikan.
* Harus dihapus setelah kebutuhan reporting selesai.

Jika export mengandung query user, anonymization policy tetap berlaku.

---

# 13. Cost Data Integrity

Usage log digunakan sebagai sumber data untuk cost monitoring.

System harus mempertahankan informasi berikut selama retention period:

```text
request_id
model
token usage
calculated cost
created_at
```

Cost calculation harus menggunakan pricing configuration yang sesuai dengan model yang digunakan.

Perubahan pricing configuration tidak boleh mengubah historical usage record yang sudah tersimpan.

Historical usage record harus dianggap immutable setelah berhasil ditulis.

---

# 14. Failure Handling

Kegagalan logging tidak boleh menyebabkan request chatbot gagal.

Contoh:

```text
Chat request    → tetap diproses
Query logging   → asynchronous
Usage logging   → asynchronous
Logging failure → dicatat sebagai application error
```

Namun, kegagalan scheduled deletion harus dimonitor dan menghasilkan operational alert agar retention requirement tetap dapat dipenuhi.

---

# 15. Audit & Compliance Verification

Implementasi retention harus dapat diverifikasi melalui:

### Session

* Review idle timeout.
* Review absolute timeout.
* Test expired session.
* Test conversation history deletion.

### Query Logs

* Test query lebih dari 30 hari terhapus.
* Test anonymization sebelum insert.
* Review access control.
* Review export authorization.

### Usage Logs

* Test `chat_usage_logs` lebih dari 90 hari terhapus.
* Test `index_usage_logs` lebih dari 90 hari terhapus.
* Review cost calculation.
* Review service-role access.

### Budget Alerts

* Test alert lebih dari 90 hari terhapus.
* Review access control.
* Review scheduled cleanup.

### Scheduled Cleanup

* Review scheduler configuration.
* Review cleanup execution log.
* Review failed cleanup events.
* Verify database records after cleanup.

---

# 16. Retention Summary

```text
Session idle timeout      : 30 minutes
Session absolute timeout  : 24 hours

Query logs                : 30 days
Chat usage logs           : 90 days
Index usage logs          : 90 days
Budget alerts             : 90 days
```

Retention period dihitung dari timestamp masing-masing record dan menggunakan UTC sebagai basis waktu database.

---

# 17. Policy Review

Retention policy harus direview apabila terdapat perubahan pada:

* PRD atau business requirement.
* Analytics requirement.
* Privacy requirement.
* Compliance requirement.
* Struktur database.
* Session management architecture.
* Logging architecture.
* Storage provider.
* Cost monitoring requirement.
* Export requirement.

Review juga harus dilakukan apabila terdapat kebutuhan untuk memperpanjang retention period.

**Current retention policy:**

```text
Session:
30 minutes idle / 24 hours absolute

Query logs:
30 days

Usage logs:
90 days

Budget alerts:
90 days
```
