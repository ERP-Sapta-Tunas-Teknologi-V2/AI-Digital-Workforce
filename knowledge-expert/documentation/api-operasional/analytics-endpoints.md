# Analytics Endpoints

Selain log export (lihat [`admin-endpoints.md`](admin-endpoints.md#log-export)), tersedia endpoint analytics tambahan untuk kebutuhan reporting.

Akses dibatasi untuk role `Admin`.

## Top FAQ

```http
GET /api/logs/top-faq?days=30&limit=5
```

Mengembalikan daftar pertanyaan yang paling sering diajukan dalam rentang hari tertentu.

| Parameter | Default | Description                          |
| --------- | ------: | -------------------------------------- |
| `days`    |      30 | Rentang hari ke belakang yang dihitung |
| `limit`   |       5 | Jumlah maksimum FAQ yang dikembalikan |

## Cost — Daily

```http
GET /api/cost/daily?date=YYYY-MM-DD
```

Mengembalikan laporan biaya (LLM/embedding) untuk satu hari tertentu. Jika `date` tidak dikirim, menggunakan tanggal berjalan.

## Cost — Weekly

```http
GET /api/cost/weekly?date=YYYY-MM-DD
```

Mengembalikan laporan biaya mingguan hingga tanggal `date` (default: hari ini).

## Cost — Budget

```http
GET /api/cost/budget
```

Mengembalikan status penggunaan budget saat ini terhadap limit yang ditentukan.

## Problematic Answers

```http
GET /api/analytics/problematic-answers?days=30&min_downvotes=1&limit=20
```

Mengembalikan daftar jawaban dengan feedback negatif (downvote) terbanyak dalam rentang hari tertentu, beserta pertanyaan, jawaban, dokumen yang dirujuk, jumlah up/downvote, dan alasan downvote.

## Flagged Documents

```http
GET /api/analytics/flagged-documents?days=30&limit=20
```

Mengembalikan daftar dokumen yang paling sering dirujuk pada jawaban yang mendapat downvote, beserta rasio downvote terhadap total kemunculan dokumen tersebut pada jawaban berfeedback. Digunakan untuk mengidentifikasi dokumen yang berpotensi perlu direvisi.

Detail lengkap request/response setiap endpoint di atas tersedia pada [`api-contract.md`](api-contract.md).
