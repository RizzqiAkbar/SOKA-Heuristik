# Real-Life Heuristic Task Scheduling (SOKA)

Implementasi penjadwalan komputasi nyata (*real-life task execution*) menggunakan Docker Compose dan arsitektur microservices untuk membandingkan performa algoritma **Max-Min**, **Min-Min**, dan **FCFS**.

---

## 🏗️ Arsitektur Sistem

- **Scheduler** (`maxmin_scheduler`): Flask API pada port `5000` yang bertanggung jawab:
  - Melakukan penemuan worker dinamis dan mendeteksi kapasitas masing-masing worker via `/health`.
  - Menghitung urutan penjadwalan (`max-min`, `min-min`, atau `fcfs`).
  - Mendistribusikan task ke antrean worker via thread pool (`ThreadPoolExecutor`).
  - Mengukur metrik komputasi nyata (*Actual Makespan*, *Throughput*, *Average Utilization*, *Degree of Imbalance*, *Gap %*).
- **Worker Containers** (`worker1` - `worker4`):
  - Mengelompok secara logis: `worker1` & `worker2` di `host1`, `worker3` & `worker4` di `host2`.
  - **Heterogen**: Memiliki kapasitas (*capacity*) yang bervariasi (`1.0`, `1.5`, `0.8`, `1.2`).
  - **Pekerjaan Riil**: Melakukan komputasi deterministik CPU-bound berupa iterasi SHA-256 yang diskalakan dengan kapasitas worker.

---

## 🚀 Cara Menjalankan

Pastikan Docker Desktop aktif di sistem Anda, lalu jalankan:

```bash
docker compose up --build -d
```

Periksa ketersediaan worker:
```bash
curl http://localhost:5000/workers
```

---

## 📊 Dataset Pengujian

Folder `datasets/` menyediakan skenario dataset task heterogen:
1. **Dataset Standar**:
   - [`datasets/dataset_10.json`](./datasets/dataset_10.json): 10 task (pengujian cepat/debug).
   - [`datasets/dataset_30.json`](./datasets/dataset_30.json): 30 task (skenario menengah).
   - [`datasets/dataset_60.json`](./datasets/dataset_60.json): 60 task (skenario komprehensif).
2. **Dataset GoCJ (Google Cloud Jobs)** (100 – 1000 Tasks):
   - [`datasets/GoCJ_Dataset_100.json`](./datasets/GoCJ_Dataset_100.json) s.d. [`datasets/GoCJ_Dataset_1000.json`](./datasets/GoCJ_Dataset_1000.json) (interval 50 task: 100, 150, 200, ..., 1000).
   - Dikonversi dari file asli `GoCJ_Dataset_<N>.txt` menggunakan script [`convert_gocj.py`](./convert_gocj.py). Workload dinormalisasi ke integer 1–100 sesuai skala komputasi riil.

Setiap task memiliki atribut `id` dan `workload` (1–100).

---

## ⚡ Menjalankan Benchmark Otomatis

Tersedia script Python `benchmark.py` untuk menguji dataset dan membandingkan ketiga algoritma secara langsung:

```bash
# Jalankan dataset standar cepat (10, 30, 60):
python benchmark.py

# Jalankan dataset GoCJ tertentu (misal: 100 task, 500 task, 1000 task):
python benchmark.py -d 100
python benchmark.py -d 500
python benchmark.py -d 1000

# Jalankan seluruh dataset GoCJ (100-1000):
python benchmark.py --gocj

# Jalankan dataset GoCJ bertahap (misal interval 200 task):
python benchmark.py --gocj-step 200

# Jalankan algoritma tertentu saja (contoh: max-min):
python benchmark.py -d 100 -a max-min
```

Hasil eksekusi akan ditampilkan berupa tabel di terminal dan otomatis diekspor ke file CSV **`hasil_benchmark.csv`** dengan metrik:
1. **Prediksi Makespan (s)**
2. **Makespan Aktual (s)**
3. **Gap (%)** = $|\text{Aktual} - \text{Prediksi}| / \text{Prediksi} \times 100$
4. **Throughput** = $\text{Task} / \text{Makespan Aktual}$
5. **Utilization (%)** = rata-rata penggunaan resource worker
6. **Degree of Imbalance** = standar deviasi beban kerja antar-worker

---

## 🧪 Pengujian Manual (API)

### PowerShell
```powershell
$body = @{
  algorithm = "max-min"
  tasks = @(
    @{ id = "T1"; workload = 4 },
    @{ id = "T2"; workload = 18 },
    @{ id = "T3"; workload = 6 },
    @{ id = "T4"; workload = 28 }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://localhost:5000/run" -Method Post -ContentType "application/json" -Body $body
```

### curl
```bash
curl -X POST http://localhost:5000/run \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"max-min","tasks":[{"id":"T1","workload":4},{"id":"T2","workload":18},{"id":"T3","workload":6}]}'
```

---

## 🛑 Menghentikan Layanan

```bash
docker compose down
```
