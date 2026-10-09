# Frontend (Vue)

Frontend utama adalah aplikasi Vue (Vuetify + Pinia) pada modul `digital-workforce`. Backend base URL diambil dari `useAuthStore().workForceUrl`.

## Komponen

| Komponen | Fungsi |
| -------- | ------ |
| `ChatBotWindow` | Area percakapan, indikator mengetik, auto-scroll |
| `ChatBotInput` | Input pesan (Enter = kirim); belum ada batas panjang di sisi klien, padahal backend menolak > 1000 karakter (`400`) |
| `ChatBotMessage` | Pesan user/assistant, daftar sumber (klik = unduh), copy, feedback up/down dengan dialog alasan opsional |
| `ChatBotSidebar` | Riwayat percakapan, search, new chat, hapus |
| `ChatProfile` | Link menuju `/digital-workforce/dashboard` |
| `Dashboard*` | Panel dashboard admin (lihat [`dashboard.md`](../api-operasional/dashboard.md)) |

## Store

| Store | Method | Endpoint |
| ----- | ------ | -------- |
| `chatbot-store` | `sendMessage` | `POST /api/chat` (SSE, header `X-User-Role`) |
| | `getSessionHistory` / `deleteSession` | `GET` / `DELETE /api/sessions/{id}` |
| | `listSessions` | `POST /api/sessions` (`user_id`) |
| | `searchSessions` | `POST /api/sessions/search` |
| | `sendFeedback` | `POST /api/feedback` |
| | `downloadSource` | `GET /api/sources/download` |
| `dashboard-store` | analytics, dokumen, approval, metadata, ingest, sync | `/api/analytics/*`, `/api/logs/*`, `/api/admin/*` (semua dengan `X-User-Role`) |

## Role

`getRoleHeader()` (`ai-role.ts`) memetakan `ai_role` akun: `admin` → `Admin`, `sales` → `Sales`, `solution_architect` → `Solution Architect`, selain itu → `Guest`. Header tidak boleh dikosongkan karena tanpa header backend tidak memfilter kategori. Header dikirim pada `/api/chat` dan semua request dashboard; request sessions, feedback, dan unduh sumber tidak mengirimnya. Role hanya klaim (lihat [`rbac-policy.md`](../kebijakan/rbac-policy.md)).

## Alur Chat

`sendMessage` membaca stream SSE dengan buffer per `\n\n` dan memanggil callback `onMetadata` (simpan `session_id`, `request_id`), `onToken`, `onAnswer`, `onSources`, `onError`, `onDone`. Feedback hanya untuk pesan yang punya `requestId`, bukan dari riwayat (`isHistory`), dan hanya sekali per pesan.

## Batasan Diketahui

* **Respons fallback JSON belum ditangani.** Bila tidak ada kandidat, backend membalas `application/json` (bukan SSE; lihat [`api-contract.md`](../api-operasional/api-contract.md)). `sendMessage` hanya mem-parse baris `data: `, sehingga jawaban fallback tidak tampil. Perlu cek `Content-Type` dan baca `answer`, `session_id`, `request_id`.
* Sidebar memakai `user_id` dari klien tanpa verifikasi (lihat [`session.md`](../kebijakan/session.md)).
