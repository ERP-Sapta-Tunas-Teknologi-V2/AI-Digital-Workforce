# Benchmark Model Lokal (T0.3 — PRD Risiko #3)

> **Status:** pemilihan model sudah cukup jelas (`qwen3.5:9b`), tetapi **kesimpulan TTFT RAG belum final**: distribusinya bimodal sehingga P90 dengan 20 sampel tidak stabil (lihat [3.1](#31-ttft-target-p90--3-s)). Penilaian manual kualitas bahasa **belum diisi**, dan `qwen3:8b` belum diuji untuk dokumen panjang.

## 1. Tujuan

Menilai kandidat model lokal pada tiga aspek:

1. Kualitas bahasa Indonesia dan Inggris.
2. Kecepatan token pertama (TTFT), target **P90 < 3 detik**.
3. Kemampuan menulis dokumen panjang.

## 2. Environment

| Item | Nilai |
| ---- | ----- |
| Runtime | Ollama (`http://localhost:11434`) |
| CPU | AMD Ryzen 7 7735HS (8 core / 16 thread) |
| RAM | 32 GB DDR5-4800 |
| GPU | NVIDIA GeForce RTX 4050 Laptop, **6 GB VRAM** (+ AMD Radeon 680M iGPU, tidak dipakai Ollama) |
| `num_ctx` / `reasoning` / `temperature` | 8192 / `False` / 0 |
| Model diuji | `qwen3.5:9b` (model saat ini), `qwen2.5:14b`, `qwen3:8b` |
| Skrip | `benchmarks/t03_benchmark.py` |
| Prompt RAG | prompt produksi (`rag/chain.py`) + 3 chunk, 4.098 token, unik per run |

Catatan hardware: ini laptop pengembangan, bukan hardware production. VRAM 6 GB hampir pasti tidak cukup untuk menampung seluruh layer model 8–14B beserta KV cache, sehingga sebagian layer berjalan di CPU. Kecepatan generation 9–11 tok/s pada model 8–9B (jauh di bawah yang lazim pada GPU penuh) konsisten dengan hal itu. Verifikasi dengan `ollama ps` (kolom PROCESSOR; harus terlihat pembagian CPU/GPU). Sebagian VRAM juga dipakai aplikasi lain (1,6 GB terpakai saat idle pada tangkapan spesifikasi).

## 3. Hasil

### 3.1 TTFT (target P90 < 3 s)

**Prompt pendek (23–42 token):** lolos pada semua model.

| Model | Cold load (s) | Cold TTFT (s) | Short P90 (s) |
| ----- | ---: | ---: | ---: |
| qwen3.5:9b  | 13,8–14,0 | 16,6–16,8 | 0,73–0,76 |
| qwen3:8b    | 8,6 | 11,1 | 0,37 |
| qwen2.5:14b | 14,1 | 16,7 | 0,75 |

**Prompt RAG (4.098 token), 20 sampel per run:**

| Model (run) | P50 (s) | Avg (s) | P90 (s) | P95 (s) | Max (s) | Run lambat |
| ----------- | ---: | ---: | ---: | ---: | ---: | :-: |
| qwen3.5:9b (run 2)  | 1,45 | 2,08 | **5,67** | ≈5,7 | 5,68 | ≥3/20 |
| qwen3.5:9b (run 3)  | 1,48 | 1,88 | **1,55** | 5,64 | 5,65 | 2/20 |
| qwen3:8b (run 3)    | 1,79 | 2,20 | **4,53** | 4,59 | 4,68 | 3/20 |
| qwen2.5:14b (run 2) | 3,55 | 4,41 | **9,28** | ≈9,4 | 9,43 | ≥3/20 |

Temuan penting:

* **Distribusi bimodal.** Sebagian besar run mengelompok rapat (qwen3.5:9b: 1,33–1,55 s; qwen3:8b: 1,56–1,92 s), sedangkan 10–15% run berada pada mode lambat yang nilainya hampir sama setiap kali (qwen3.5:9b ≈5,65 s; qwen3:8b ≈4,6 s; qwen2.5:14b ≈9,4 s).
* **P90 dengan 20 sampel tidak stabil.** Dengan 2 run lambat dari 20, P90 lolos (1,55 s); dengan 3 run lambat, P90 gagal (5,67 s). Model yang sama menghasilkan kedua hasil di dua run berbeda, jadi selisih P90 antara qwen3.5:9b dan qwen3:8b pada tabel ini **bukan** bukti salah satunya lebih cepat. Pada P95, kedua model gagal (> 4,5 s).
* **Penyebab mode lambat belum terkonfirmasi.** Hipotesis: (a) mode cepat sebenarnya masih memanfaatkan sebagian cache sedangkan mode lambat adalah evaluasi prompt penuh (≈720 tok/s); (b) mode lambat disebabkan hal di sisi hardware (pembagian layer CPU/GPU, tekanan VRAM, power state). Kecepatan prompt evaluation mode cepat (≈4.100 tok/s menurut Ollama) terlalu tinggi untuk mesin yang generation-nya hanya ±10 tok/s, sehingga hipotesis (a) belum bisa dikesampingkan; skrip menandainya sebagai "⚠ cache?".
* **Overhead tetap.** Prompt pendek memakan ±0,7 s pada qwen3.5:9b dan ±0,37 s pada qwen3:8b meskipun hanya 23–30 token.
* Cold start 8,6–14 detik; pertahankan `OLLAMA_KEEP_ALIVE`.

### 3.2 Kecepatan generation

| Model | Tok/s (prompt pendek) | Tok/s (konteks RAG) | Tok/s (dokumen panjang) |
| ----- | ---: | ---: | ---: |
| qwen3.5:9b  | 10,2 | 11,3–11,4 | 7,7–7,9 |
| qwen3:8b    | 15,4 | 8,9 | belum diuji |
| qwen2.5:14b | 4,1  | 3,2 | 3,6–3,7 |

Pada ±11 tok/s jawaban 300 token selesai dalam ±27 detik (mendekati batas SLA generation P95 ≤ 30 s). qwen3:8b lebih cepat pada prompt pendek tetapi turun menjadi 8,9 tok/s dengan konteks RAG, sehingga lebih lambat dari qwen3.5:9b pada skenario yang relevan.

### 3.3 Kualitas bahasa

Auto-check (bahasa output dan format) lolos 5/5 pada semua model, baik Indonesia maupun Inggris, sehingga tidak membedakan kandidat. Penilaian manual (`t03_manual_rating_*.csv`) **belum diisi**.

Pengamatan awal (bukan pengganti penilaian manual):

* **qwen3.5:9b** — penjelasan lebih natural (analogi restoran untuk SLA vs SLO), email lengkap dengan placeholder; satu salah ketik ("berwenu").
* **qwen3:8b** — lebih datar dan generik; email membuka dengan "Salam hormat" sebelum isi dan alasan penundaan kurang spesifik; ada frasa janggal ("yang memaksa perlindungan data").
* **qwen2.5:14b** — terjemahan terlalu harfiah ("saat beristirahat" untuk *at rest*), pengulangan kata ("handal dan andal"), frasa kaku pada email.

### 3.4 Dokumen panjang (permintaan: 6 bagian, ≥ 1000 kata)

Diuji pada run 2 (`qwen3:8b` belum diuji).

| Model | Tes | Kata | Bagian | Distinct trigram | Terpotong | Total (s) |
| ----- | --- | ---: | :-: | ---: | :-: | ---: |
| qwen3.5:9b  | long_id | 1759 | 6/6 | 0.99 | tidak | 341 |
| qwen3.5:9b  | long_en | 1744 | 6/6 | 0.99 | tidak | 285 |
| qwen2.5:14b | long_id | **845** | 6/6 | 0.93 | tidak | 535 |
| qwen2.5:14b | long_en | 1755 | 6/6 | **0.81** | tidak | 598 |

qwen3.5:9b konsisten antar run (jumlah kata sama persis) dan tanpa repetisi. qwen2.5:14b tidak konsisten (973 → 845 kata untuk Indonesia; 1175 → 1755 untuk Inggris) dan gagal memenuhi minimum 1000 kata pada tes Indonesia di kedua run.

## 4. Catatan Metodologi

* Run 1 (`20261008_141230`) **tidak valid** untuk TTFT RAG: prompt identik membuat Ollama memakai ulang KV cache (TTFT 0,3–0,4 s). Diabaikan.
* Run 2 (`20261009_092911`) dan run 3 (`20261009_104236`) memakai prompt unik per run (penanda unik di awal tiap chunk), tetapi isi chunk sama; efek reuse parsial belum dikesampingkan. Run berikutnya sebaiknya mengacak isi konteks per run dan memakai ≥ 50 sampel.
* P90 dari 20 sampel hanya bergantung pada apakah ≥ 3 sampel berada di mode lambat. Laporkan juga P95/max dan jumlah run lambat.
* TTFT yang dirasakan user di production lebih besar dari angka di atas karena ada contextualizer (satu panggilan LLM tambahan), embedding (±7 s pada [baseline](performance-sla.md)), dan riwayat percakapan.

## 5. Rekomendasi

1. **Pertahankan `qwen3.5:9b` sebagai model utama.** Kualitas bahasa awal terbaik, generation tercepat pada skenario RAG, dan konsisten pada dokumen panjang. `qwen2.5:14b` **dicoret** (2–3× lebih lambat, gagal panjang dokumen, repetisi). `qwen3:8b` hanya menjadi cadangan (cold load lebih cepat, tetapi generation dengan konteks RAG lebih lambat dan kualitas awal lebih rendah); layak dipertimbangkan kembali hanya jika uji dokumen panjang dan penilaian manual baik.
2. **TTFT RAG: status "belum dapat disimpulkan".** Mode cepat (±1,4 s) lolos, tetapi 10–15% request berada di mode lambat (±5,7 s) sehingga P95 gagal. Langkah: (a) jalankan ulang dengan isi konteks diacak per run dan ≥ 50 sampel; (b) periksa `ollama ps` untuk pembagian CPU/GPU; (c) kecilkan konteks (chunk ±500 token atau `rerank_k` 2) dan ukur ulang; (d) bila mode lambat berasal dari keterbatasan VRAM, tutup aplikasi yang memakai GPU atau coba `OLLAMA_FLASH_ATTENTION=1` dengan `OLLAMA_KV_CACHE_TYPE=q8_0` untuk menghemat VRAM.
3. **Hardware production harus diverifikasi.** Target SLA berlaku untuk production, bukan laptop ini. Pastikan seluruh layer model dan KV cache muat di VRAM (`ollama ps` menunjukkan 100% GPU), lalu ulangi benchmark.
4. **Batasi panjang jawaban** (±300 token pada kecepatan ±11 tok/s) agar sesuai SLA generation 30 detik.
5. **Dokumen panjang (±1750 kata) membutuhkan ±5 menit** pada hardware ini; jalankan sebagai tugas latar belakang/streaming dengan indikator progres.

## 6. Risiko Tersisa (PRD #3)

| Risiko | Status | Mitigasi |
| ------ | ------ | -------- |
| TTFT RAG: ekor lambat 10–15% (±5,7 s) | Terukur, penyebab belum pasti | Uji ulang dengan konteks diacak; periksa offload CPU/GPU; kecilkan konteks |
| Generation lambat (±11 tok/s) | Terukur di laptop 6 GB VRAM | Batasi panjang jawaban; hardware production dengan VRAM memadai |
| Hasil benchmark di laptop tidak mewakili production | Terindikasi | Ulangi pada hardware production |
| Kefasihan bahasa Indonesia | Pengamatan awal saja | Penilaian manual ≥ 2 penilai; fallback ke model lain jika skor < 4 |

## 7. Langkah Berikutnya

* [ ] Isi `t03_manual_rating_*.csv` (minimal 2 penilai, tanpa melihat nama model).
* [ ] Jalankan `ollama ps` saat benchmark berlangsung dan catat pembagian CPU/GPU.
* [ ] Ubah skrip agar isi konteks diacak per run, lalu jalankan `--runs 50` untuk `qwen3.5:9b`.
* [ ] (Opsional) Uji dokumen panjang untuk `qwen3:8b` tanpa `--skip-long`.
* [ ] Uji ulang dengan konteks diperkecil (chunk ±500 token atau `rerank_k=2`).
* [ ] Ulangi pada hardware production bila tersedia, lalu finalisasi status target TTFT.
