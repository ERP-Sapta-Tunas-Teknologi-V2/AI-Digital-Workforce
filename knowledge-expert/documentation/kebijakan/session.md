# Session Management

## ⚠️ Status Implementasi

Kolom `expires_at` dan `absolute_expires_at` **belum ada** pada tabel `sessions` (lihat `supabase.sql`).
`SupabaseSessionStore.touch()` saat ini hanya memperbarui `last_activity_at`, tanpa menghitung ulang expiry.
`SupabaseSessionStore.cleanup()` saat ini adalah stub (`return 0`) — belum melakukan penghapusan session expired.
Idle timeout dan absolute timeout pada dokumen ini merupakan **target desain**, bukan perilaku aktual saat ini.

Referensi: [retention-policy.md](retention-policy.md#36-session-deletion) dan [database-schema.md](../referensi-teknis/database-schema.md#sessions)

## 1. Objective

Mendefinisikan lifecycle, struktur, penyimpanan, dan penggunaan session pada chatbot untuk mendukung multi-turn conversation.

Session management harus memastikan:

* Setiap conversation memiliki session yang unik.
* Conversation history terisolasi antar session.
* Follow-up question dapat menggunakan context conversation sebelumnya.
* Session memiliki batas waktu yang jelas.
* Session expired tidak dapat menggunakan conversation history.
* Conversation history tidak dikirim ke LLM setelah session expired.
* Struktur dapat digunakan dengan in-memory, database, maupun Redis.
* Penyimpanan conversation mengikuti security, privacy, dan retention policy.

## 2. Session Policy

| Parameter           | Policy                                       |
| ------------------- | -------------------------------------------- |
| Idle timeout        | 30 menit                                     |
| Absolute timeout    | 24 jam                                       |
| Session ID          | UUID v4                                      |
| Storage production  | Database / Redis                             |
| Storage development | In-memory diperbolehkan                      |
| Expired session     | Tidak dapat menggunakan conversation history |
| Cleanup             | Session expired dihapus secara berkala       |

## 2.1 Idle Timeout

Session dianggap expired apabila tidak terdapat aktivitas selama **30 menit**.

Setiap request yang valid dari session aktif akan memperbarui waktu aktivitas dan expiry.

Contoh:

```text
13:00  Session dibuat
       expires_at = 13:30

13:10  User mengirim follow-up
       expires_at = 13:40

13:35  User mengirim follow-up
       expires_at = 14:05

14:06  User mengirim request
       session expired
       → history lama tidak digunakan
       → session baru dibuat
```

Idle timeout tidak boleh memperpanjang session melewati absolute timeout.

## 2.2 Absolute Timeout

Session memiliki batas maksimum **24 jam** sejak session dibuat.

Aktivitas user tidak boleh memperpanjang session melewati absolute timeout.

Contoh:

```text
08:00  Session dibuat
       absolute_expiry = 08:00 hari berikutnya

07:50  User masih aktif
       session tetap aktif

08:01  Session expired
       → session baru dibuat
```

Absolute timeout digunakan untuk memastikan session tidak dapat hidup tanpa batas waktu.

## 2.3 Session Expiry

Session dianggap expired apabila salah satu kondisi terpenuhi:

```text
current_time >= expires_at
```

atau:

```text
current_time >= absolute_expires_at
```

Session harus dianggap tidak aktif apabila salah satu batas tersebut tercapai.

## 2.4 Expired Session Behavior

Apabila request menggunakan session yang sudah expired:

1. Session dianggap tidak aktif.
2. Conversation history session tersebut tidak digunakan.
3. History lama tidak dikirim ke RAG atau LLM.
4. Session baru dibuat.
5. Request diproses menggunakan session baru.
6. Session lama menunggu proses cleanup sesuai retention policy.

Contoh:

```text
Request
   │
   ▼
Check Session
   │
   ├── Active
   │     └── Load history
   │
   └── Expired
         ├── Ignore old history
         ├── Create new session
         └── Process request
```

## 2.5 Cleanup

Expired session dan conversation history yang terkait harus dibersihkan secara berkala.

Cleanup dapat dilakukan menggunakan:

* Scheduled job.
* Background worker.
* Database cleanup query.
* Redis TTL apabila Redis digunakan.

Cleanup tidak boleh menghapus session yang masih aktif.

Cleanup juga harus mengikuti retention policy yang ditentukan pada bagian compliance.

# 3. Session Structure

## 3.1 Session Identifier

Setiap session memiliki identifier berupa **UUID v4**.

`session_id` digunakan untuk menghubungkan request dengan conversation history.

Jika request tidak memiliki `session_id`, application membuat session baru.

## 3.2 Session Data

Minimal setiap session menyimpan:

```text
session_id
created_at
last_activity_at
expires_at
absolute_expires_at
```

## 3.3 User Association

Jika application memiliki authentication, session dapat dikaitkan dengan `user_id`.

Struktur:

```text
sessions
├── session_id
├── user_id
├── created_at
├── last_activity_at
├── expires_at
└── absolute_expires_at
```

`user_id` tidak menggantikan `session_id`.

Satu user dapat memiliki beberapa session:

```text
user_001
├── session_A
├── session_B
└── session_C
```

Setiap session memiliki conversation history yang terpisah.

Jika chatbot belum memiliki authentication, `user_id` dapat ditiadakan dan session cukup menggunakan `session_id`.

# 4. Conversation History

## 4.1 Message Structure

Conversation history disimpan berdasarkan `session_id`.

Struktur:

```text
conversation_messages
├── id
├── session_id
├── role
├── content
└── created_at
```

## 4.2 Supported Roles

Conversation history menggunakan role:

```text
user
assistant
```

System prompt tidak disimpan sebagai conversation history user.

System prompt tetap dikelola oleh application.

User input tidak boleh digunakan untuk menggantikan atau memodifikasi system prompt.

## 4.3 Conversation Ordering

Message harus memiliki urutan berdasarkan waktu atau sequence.

Contoh:

```text
1. user
2. assistant
3. user
4. assistant
5. user
6. assistant
```

History harus dikirim ke LLM dalam urutan conversation yang benar.

## 4.4 Context Isolation

Conversation context harus terisolasi berdasarkan `session_id`.

Contoh:

```text
User A
└── Session A1
    ├── Message 1
    └── Message 2

User A
└── Session A2
    ├── Message 1
    └── Message 2

User B
└── Session B1
    ├── Message 1
    └── Message 2
```

History `A1` tidak boleh digunakan oleh `A2`.

History `A1` dan `A2` juga tidak boleh digunakan oleh `B1`.

# 5. Conversation Context

## 5.1 Context Retrieval

Pada setiap request:

```text
Request
   │
   ├── session_id
   └── question
   │
   ▼
Validate Session
   │
   ├── Expired
   │     └── Create new session
   │
   └── Active
         │
         ▼
   Load Conversation History
         │
         ▼
   Build Conversation Context
         │
         ▼
   RAG Retrieval
         │
         ▼
   LLM
```

Conversation history hanya boleh diambil apabila session masih aktif.

## 5.2 Context Composition

Context untuk LLM dapat terdiri dari:

```text
System Prompt
+
Recent Conversation History
+
RAG Context
+
Current User Question
```

RAG context tetap menjadi sumber utama informasi faktual chatbot.

Conversation history digunakan terutama untuk memahami referensi dan konteks follow-up question.

## 5.3 Context Window

Tidak seluruh conversation history harus selalu dikirim ke LLM.

History harus dibatasi berdasarkan context window dan kebutuhan conversation.

Strategi awal:

```text
Recent conversation history
+
Current question
+
Relevant RAG context
```

History lama dapat dikeluarkan apabila menyebabkan context melebihi batas token.

Jika diperlukan, history dapat diringkas menggunakan conversation summary pada tahap implementasi berikutnya.

# 6. Follow-up Question

## 6.1 Purpose

Session context digunakan agar user dapat mengajukan pertanyaan lanjutan tanpa harus mengulang konteks sebelumnya.

Pertanyaan kedua membutuhkan context dari pertanyaan dan jawaban sebelumnya.

## 6.2 Contextual Question

Apabila session memiliki conversation history, application dapat menggunakan
LLM contextualizer untuk mengubah current question menjadi standalone question.

Contextualizer hanya digunakan untuk membantu retrieval.

Flow:

```text
Conversation History
        +
Current Question
        ↓
Contextualizer
        ↓
Standalone Question
        ↓
RAG Retrieval
```

Standalone question digunakan untuk retrieval.

Current question asli tetap digunakan sebagai pertanyaan user untuk final answer.

```text
Contextual Question
→ Retrieval

Original Question
→ Final LLM
```

Contextualizer tidak boleh menjawab pertanyaan.

Apabila session tidak memiliki history, contextualization tidak diperlukan
dan current question langsung digunakan untuk retrieval.

## 6.3 RAG and Conversation History

Conversation history dan RAG memiliki fungsi berbeda:

```text
Conversation History
→ memahami konteks conversation

RAG
→ mengambil informasi dari knowledge base

LLM
→ menghasilkan jawaban berdasarkan conversation context + RAG context
```

Conversation history tidak boleh dianggap sebagai pengganti knowledge base.

Informasi faktual tetap harus berasal dari knowledge base sesuai aturan RAG chatbot.

# 7. API Structure

## 7.1 Request dengan Session

Request dapat menggunakan:

```json
{
  "session_id": "...",
  "question": "..."
}
```

## 7.2 Request tanpa Session

Jika user memulai conversation:

```json
{
  "question": "..."
}
```

Application membuat session baru.

## 7.3 Response

Response mengembalikan `session_id`:

```json
{
  "session_id": "...",
  "answer": "..."
}
```

Client menggunakan `session_id` tersebut untuk request berikutnya.

## 7.4 Expired Session Response

Apabila client mengirim `session_id` yang expired, application membuat session baru.

Contoh:

```json
{
  "session_id": "new-session-uuid",
  "answer": "..."
}
```

Client harus menggunakan `session_id` baru untuk request berikutnya.

# 7.5 Sidebar Riwayat Percakapan

Widget chat publik (`/`) menampilkan daftar percakapan sebelumnya pada sidebar.

## 7.5.1 Prinsip

Karena widget chat publik tidak memiliki authentication, kepemilikan daftar percakapan ditentukan oleh **browser client**, bukan oleh backend:

```text
Backend
→ tidak menyimpan mapping "session_id milik siapa"

Client (localStorage)
→ menyimpan daftar session_id yang pernah dibuat oleh browser tersebut
```

Konsekuensinya, `session_id` harus tetap diperlakukan sebagai identifier sensitif (lihat [10.2](#102-session-id)) karena siapa pun yang mengetahui `session_id` dapat mengambil maupun menghapus riwayatnya melalui endpoint terkait, tanpa validasi ownership.

## 7.5.2 Judul Percakapan

Judul (`title`) diisi otomatis dari potongan pertanyaan pertama user (maksimal 40 karakter) saat session baru dibuat, dan ditampilkan pada sidebar untuk membedakan setiap percakapan.

## 7.5.3 Sumber pada Riwayat Pesan

Setiap pesan `assistant` yang dihasilkan dari jawaban RAG (bukan fallback) menyimpan metadata dokumen yang dirujuk (`sources`) bersama isi jawabannya. Tujuannya agar saat percakapan lama dibuka kembali dari sidebar, sitasi/sumber yang ditampilkan pada jawaban tetap konsisten dengan yang muncul saat jawaban pertama kali diberikan, tanpa perlu retrieval ulang.

Field yang disimpan mengikuti field yang sama dengan `metadata.sources` pada respons `/api/chat` (lihat [Sources](../api-operasional/api-contract.md#sources)), bukan objek metadata mentah internal (`retrieval_score`, `rerank_score`, `chunk_index`, `fingerprint`, `content`, `embedding` tidak disimpan).

Pesan `user` dan jawaban fallback (`"Informasi tidak ditemukan..."`) tidak memiliki `sources`.

## 7.5.4 Endpoint Terkait

| Endpoint                     | Method | Fungsi                                                  |
| ------------------------------ | ------ | ---------------------------------------------------------- |
| `POST /api/sessions`          | POST   | Mengambil metadata sejumlah session (title, waktu) berdasarkan daftar `session_id` yang dikirim client. |
| `GET /api/sessions/<id>`      | GET    | Mengambil riwayat pesan lengkap satu session untuk ditampilkan ulang di chat window. |
| `DELETE /api/sessions/<id>`   | DELETE | Menghapus session beserta seluruh riwayat pesannya (cascade). |

Detail request/response tersedia pada [`api-contract.md`](../api-operasional/api-contract.md#sessions-sidebar).

## 7.5.5 Penghapusan Percakapan

User dapat menghapus percakapan dari sidebar. Penghapusan bersifat permanen:

```text
DELETE /api/sessions/<id>
        │
        ▼
sessions row dihapus
        │
        ▼
session_messages ikut terhapus (on delete cascade)
        │
        ▼
Client menghapus session_id dari localStorage
```

Tidak ada mekanisme undo setelah penghapusan dilakukan.

# 8. Storage

## 8.1 Production

Production menggunakan salah satu: **Database** atau **Redis**.

Database cocok apabila conversation history perlu disimpan secara persistent.

Redis cocok apabila session membutuhkan akses cepat dan TTL native.

## 8.2 Storage Implementation

Storage session menggunakan Supabase (`public.sessions` dan `public.session_messages`), bukan in-memory, agar history tetap tersedia setelah aplikasi restart dan mendukung fitur riwayat percakapan (sidebar) pada widget chat.

Struktur implementasi:

```text
SessionManager
    │
    ▼
SupabaseSessionStore
    │
    ├── sessions           (metadata session)
    └── session_messages   (riwayat pesan)
```

In-memory store tidak lagi digunakan pada implementasi saat ini, termasuk pada development, karena sidebar riwayat percakapan membutuhkan data yang persist antar reload halaman.

## 8.3 Database Structure

Relasi:

```text
sessions
    │
    │ 1:N
    ▼
conversation_messages
```

Contoh:

```text
sessions
┌─────────────────────────┐
│ session_id PK           │
│ user_id                 │
│ created_at              │
│ last_activity_at        │
│ expires_at              │
│ absolute_expires_at     │
└────────────┬────────────┘
             │
             │ 1:N
             ▼
conversation_messages
┌─────────────────────────┐
│ id PK                   │
│ session_id FK           │
│ role                    │
│ content                 │
│ created_at              │
└─────────────────────────┘
```

`conversation_messages.session_id` harus memiliki foreign key ke `sessions.session_id`.

Index pada `session_id` disarankan untuk mempercepat pengambilan history.

## 8.4 Redis

Jika Redis digunakan, session dapat menggunakan TTL.

Contoh konsep:

```text
session:{session_id}
conversation:{session_id}
```

TTL session mengikuti idle timeout.

Absolute timeout tetap harus divalidasi oleh application agar session tidak hidup lebih dari 24 jam.

# 9. Session Lifecycle

Lifecycle session:

```text
             ┌─────────────┐
             │   Created   │
             └──────┬──────┘
                    │
                    ▼
             ┌─────────────┐
             │    Active   │◄──── Request
             └──────┬──────┘
                    │
             ┌──────┴──────┐
             │             │
             ▼             ▼
        Idle timeout   Absolute timeout
             │             │
             └──────┬──────┘
                    ▼
             ┌─────────────┐
             │   Expired   │
             └──────┬──────┘
                    │
                    ▼
             ┌─────────────┐
             │   Cleanup   │
             └─────────────┘
```

# 10. Security & Privacy

## 10.1 Session Isolation

Session hanya boleh mengakses conversation history miliknya sendiri.

Request tidak boleh mengambil history hanya berdasarkan `user_id` jika `session_id` tersedia sebagai identifier conversation.

## 10.2 Session ID

`session_id` harus dianggap sebagai identifier sensitif terhadap akses conversation.

Application harus melakukan validasi ownership apabila authentication tersedia.

User tidak boleh dapat mengakses session milik user lain hanya dengan mengetahui `session_id`.

## 10.3 Conversation History

Conversation history tidak boleh dikirim ke LLM apabila session sudah expired.

History juga tidak boleh digunakan untuk retrieval setelah session expired.

## 10.4 PII

Conversation history yang mengandung PII harus mengikuti privacy dan compliance policy.

Jika consent diperlukan sebelum penyimpanan conversation history, application harus memastikan consent telah diberikan sebelum data disimpan.

## 10.5 System Prompt

Conversation history tidak boleh digunakan untuk mengubah system prompt.

User input harus diperlakukan sebagai data conversation, bukan sebagai instruction yang memiliki prioritas lebih tinggi daripada system prompt.

# 11. Retention

Session expiry dan data retention merupakan dua konsep berbeda.

```text
Session expiry
→ menentukan apakah session masih dapat digunakan.

Data retention
→ menentukan berapa lama data expired tetap disimpan.
```

Contoh:

```text
Session active
     │
     │ 30 menit idle
     ▼
Session expired
     │
     │ retention period
     ▼
Data deleted
```

Retention period untuk session dan conversation history mengikuti Compliance Retention Policy.

# 12. Implementation Rules

1. Setiap session menggunakan UUID v4.
2. Setiap conversation message memiliki `session_id`.
3. Session memiliki idle timeout 30 menit.
4. Session memiliki absolute timeout 24 jam.
5. Request aktif memperbarui idle timeout.
6. Idle timeout tidak boleh melewati absolute timeout.
7. Session expired tidak boleh menggunakan conversation history.
8. History session expired tidak boleh dikirim ke RAG atau LLM.
9. Session expired tidak boleh digunakan untuk conversation berikutnya.
10. Session baru dibuat apabila `session_id` tidak tersedia atau sudah expired.
11. Conversation history harus terisolasi berdasarkan `session_id`.
12. Jika authentication tersedia, session harus dikaitkan dengan `user_id`.
13. Conversation history harus dibatasi berdasarkan context/token limit.
14. RAG tetap menjadi sumber utama informasi faktual.
15. System prompt dikelola oleh application.
16. Cleanup tidak boleh menghapus session yang masih aktif.
17. Retention data mengikuti Compliance Retention Policy.
18. Production menggunakan Database atau Redis.
19. In-memory storage hanya digunakan untuk development/testing.
20. Session ownership harus divalidasi apabila authentication tersedia.