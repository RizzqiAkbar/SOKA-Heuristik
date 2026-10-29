# Max-Min Scheduling Self-Hosted Demo

## Arsitektur
- Scheduler: Flask API pada port 5000.
- Empat worker container: worker1 sampai worker4.
- Pengelompokan logis: worker1/worker2 = host1; worker3/worker4 = host2.
- Semua container berjalan pada satu laptop menggunakan Docker Compose. Ini bukan dua host fisik/VM terpisah.

## Menjalankan
Pastikan Docker Desktop aktif, lalu dari folder proyek:

```bash
docker compose up --build
```

Cek worker:
```bash
curl http://localhost:5000/workers
```

## Menguji Max-Min (PowerShell)
```powershell
$body = @{
  algorithm = "max-min"
  tasks = @(
    @{ id = "T1"; workload = 4 },
    @{ id = "T2"; workload = 8 },
    @{ id = "T3"; workload = 3 },
    @{ id = "T4"; workload = 9 },
    @{ id = "T5"; workload = 5 }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://localhost:5000/run" -Method Post -ContentType "application/json" -Body $body
```

Ganti `algorithm` menjadi `min-min` atau `fcfs` untuk membandingkan algoritma.

## Pengujian dengan curl
```bash
curl -X POST http://localhost:5000/run \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"max-min","tasks":[{"id":"T1","workload":4},{"id":"T2","workload":8},{"id":"T3","workload":3}]}'
```

## Menghentikan
```bash
docker compose down
```

## Catatan
- `workload` harus bilangan bulat 1 sampai 100.
- Worker menjalankan komputasi SHA-256 berulang sebagai pekerjaan nyata untuk pengujian.
- Estimasi Max-Min menggunakan workload / kapasitas baseline. Semua worker saat ini memakai kapasitas yang sama.
- Makespan dan throughput diukur dari eksekusi aktual pada container lokal; angka dapat berubah antarpengujian.
- Ini demo pembelajaran, bukan konfigurasi produksi. Flask development server dan workload komputasi tidak ditujukan untuk akses publik.
