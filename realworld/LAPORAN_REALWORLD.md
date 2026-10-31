# Implementasi Max-Min di Cluster Kubernetes Nyata

Draf bagian "Real World" untuk laporan. Angka diambil dari keluaran run yang tersimpan di
`hasil_ringkas.txt`, `hasil_ringkas_2.txt`, dan README folder ini. Kalimat yang diberi label **(dugaan)** belum diuji secara terpisah.

## 1. Tujuan

Menjalankan heuristik Max-Min pada infrastruktur nyata (bukan simulator), lalu membandingkan makespan hasil
simulasi (prediksi) dengan makespan yang diukur di cluster.

## 2. Topologi

| Komponen | Jumlah | Keterangan |
|---|---|---|
| Datacenter | 1 | 1 cluster Kubernetes (k3s v1.36.5) |
| Host fisik | 2 | PC 1 (Windows Pro, driver Hyper-V) dan PC 2 (Windows Home, driver HCS), RAM 8 GB, jaringan WiFi berbeda |
| VM | 4 | 2 VM per host, Ubuntu 24.04, dibuat dengan Multipass |
| Penghubung | Tailscale | VPN antar-VM di dua jaringan berbeda |

| VM | Host | vCPU | RAM | Peran | Kecepatan hasil kalibrasi |
|---|---|---|---|---|---|
| vm-a1 | PC 1 | 2 | 2 GB | k3s server + worker | 13,0 juta iterasi/detik |
| vm-a2 | PC 1 | 1 | 1,5 GB | worker | 14,5 juta iterasi/detik |
| vm-b1 | PC 2 | 2 | 2 GB | worker | 13,8 juta iterasi/detik |
| vm-b2 | PC 2 | 1 | 1,5 GB | worker | 15,2 juta iterasi/detik |

Total 6 vCPU. VM bersifat heterogen dalam jumlah vCPU dan RAM.

Konfigurasi simulasi pada repo ini berbeda (parameter di `Main.java`: 3 datacenter, 5 host per datacenter,
2 VM per host). Real world memakai topologi yang lebih kecil karena keterbatasan perangkat.

## 3. Metode

1. **Kalibrasi.** `calibrate.py` menjalankan satu Job per vCPU di setiap node secara serentak, di dalam container
   yang sama dengan task, lalu mencatat kecepatan (iterasi per detik) tiap node.
2. **Plan Max-Min.** `RealWorldPlanner` memuat dataset GoCJ (`GoCJ_Dataset_N.txt`), membuat VM simulasi dengan
   kecepatan hasil kalibrasi, lalu menjalankan Max-Min yang sama dengan yang dipakai pada simulasi. Keluarannya
   `plan.csv`: urutan task, node tujuan, dan jumlah iterasi.
3. **Skala.** Panjang task (MI) dikalikan satu faktor yang sama sehingga makespan prediksi sama dengan target
   waktu yang dipilih. Faktor seragam tidak mengubah keputusan Max-Min: pembagian task ke node sama dengan di simulasi.
   Prediksi adalah makespan simulasi Max-Min untuk keempat node dengan panjang task yang sudah diskalakan.
4. **Eksekusi.** `run_plan.py` membuat satu Kubernetes Job per task, dipaksa ke node pilihan Max-Min
   (`nodeSelector`). Node dengan N vCPU menjalankan paling banyak N task bersamaan, sisanya antre sesuai urutan
   Max-Min (setara `CloudletSchedulerSpaceShared`).
5. **Beban kerja.** Satu task = loop CPU Python sebanyak `iterations` di image `python:3.12-alpine`.
   Beban ini sintetis agar dapat diulang dan dibandingkan dengan simulasi.
6. **Pengukuran.** Makespan = waktu penyelesaian task terakhir dikurangi waktu pembuatan Job pertama
   (timestamp Kubernetes, resolusi 1 detik). Utilisasi node = total waktu sibuk task dibagi (vCPU x makespan).

## 4. Hasil

### 4.1 Pembagian dan makespan (target = 3 x jumlah task)

| Task | Prediksi | Aktual | Selisih | Throughput (task/detik) |
|---|---|---|---|---|
| 100 | 300 detik | 461 detik | 53,7% | 0,217 |
| 200 | 600 detik | 836 detik | 39,3% | 0,239 |
| 300 | 900 detik | 1210 detik | 34,4% | 0,248 |
| 400 | 1200 detik | 1704 detik | 42,0% | 0,235 |
| 500 | 1500 detik | 2024 detik | 34,9% | 0,247 |
| 600 | 1800 detik | 2628 detik | 46,0% | 0,228 |
| 700 | 2100 detik | 2792 detik | 33,0% | 0,251 |
| 800 | 2400 detik | 3405 detik | 41,9% | 0,235 |
| 900 | 2700 detik | 3808 detik | 41,0% | 0,236 |
| 1000 | 3000 detik | 5072 detik | 69,1% | 0,197 |

Rata-rata panjang task pada plan ini sekitar 18 detik (6 vCPU x target / jumlah task).

### 4.2 Jumlah task dan utilisasi per node

| Task | vm-a1 (2 vCPU) | vm-a2 (1 vCPU) | vm-b1 (2 vCPU) | vm-b2 (1 vCPU) |
|---|---|---|---|---|
| 100 | 32 task, 95,6% | 16 task, 96,7% | 33 task, 60,5% | 19 task, 68,5% |
| 200 | 63 task, 95,9% | 34 task, 95,7% | 67 task, 64,1% | 36 task, 70,5% |
| 300 | 95 task, 93,3% | 52 task, 94,8% | 98 task, 66,0% | 55 task, 72,4% |
| 400 | 126 task, 95,0% | 69 task, 94,3% | 132 task, 56,9% | 73 task, 63,8% |
| 500 | 159 task, 92,7% | 86 task, 95,0% | 165 task, 63,1% | 90 task, 70,5% |
| 600 | 188 task, 94,5% | 105 task, 94,0% | 198 task, 55,4% | 109 task, 61,3% |
| 700 | 219 task, 93,6% | 121 task, 93,2% | 233 task, 61,6% | 127 task, 68,9% |
| 800 | 253 task, 94,4% | 139 task, 92,7% | 262 task, 57,0% | 146 task, 63,2% |
| 900 | 284 task, 93,6% | 156 task, 92,9% | 296 task, 57,3% | 164 task, 64,2% |
| 1000 | 314 task, 93,5% | 173 task, 89,6% | 330 task, 47,7% | 183 task, 53,0% |

Node dengan 2 vCPU mendapat sekitar dua kali lipat task dibanding node dengan 1 vCPU pada semua ukuran.

### 4.3 Pengaruh panjang task (100 task, plan pemanasan dan plan target 600)

| Plan | Task rata-rata | Prediksi | Aktual | Selisih |
|---|---|---|---|---|
| Pemanasan (3 kali run) | sekitar 3,6 detik | 60 detik | 162, 153, 126 detik | 170%, 155%, 110% |
| Target 300 (4.1) | sekitar 18 detik | 300 detik | 461 detik | 53,7% |
| Target 600 | sekitar 36 detik | 600 detik | 754 detik | 25,7% |

## 5. Analisis

**Aktual selalu lebih besar dari prediksi.** Simulasi mengasumsikan task langsung berjalan dan setiap VM memiliki
CPU sendiri. Di cluster nyata ada biaya yang tidak dimodelkan simulasi.

**Selisih mengecil saat task lebih panjang (terukur).** Pada 100 task, selisih turun dari 110-170% (task sekitar
3,6 detik) menjadi 53,7% (sekitar 18 detik) dan 25,7% (sekitar 36 detik). Ini konsisten dengan adanya biaya tetap
per task (membuat Job, menjadwalkan pod, memulai container) yang makin kecil porsinya bila task lebih panjang.
Biaya per task itu sendiri belum diukur langsung **(dugaan mekanisme)**.

**Setelah 200 task selisih berkisar 33-46% tanpa tren jelas (terukur).** Pada 300-900 task throughput berada di
0,23-0,25 task/detik. Naik-turunnya (misalnya 33,0% pada 700 dan 46,0% pada 600 task) kemungkinan variasi antar-run:
tiap ukuran hanya satu run dan plan pemanasan yang sama pernah menghasilkan 162, 153, dan 126 detik.

**1000 task paling lambat (terukur).** Selisih 69,1%, throughput 0,197 task/detik, dan utilisasi semua node turun
(vm-a2 89,6%; vm-b1 47,7%; vm-b2 53,0%). Penyebabnya belum diukur. **(Dugaan)** `run_plan.py` menyimpan 1000 Job dan
meminta daftar Job tiap detik di vm-a1 (2 vCPU, 2 GB, juga k3s server), sehingga pengendali itu sendiri melambat.

**Utilisasi tidak merata antar-PC (terukur).** Pada 100-900 task, vm-a1 dan vm-a2 (PC 1) 93-97%, vm-b1 dan vm-b2
(PC 2) 55-72%. `tailscale status` menunjukkan vm-b1 dan vm-b2 terhubung ke PC 1 lewat relay Tailscale, sedangkan
vm-a2 terhubung langsung (terukur). **(Dugaan)** server k3s berada di PC 1 sehingga laporan penyelesaian task dari
PC 2 tertunda oleh relay, dan task berikutnya dibuat lebih lambat sehingga node PC 2 memiliki jeda kosong. Dugaan
lain: k3s server dan `run_plan.py` memakai CPU vm-a1, serta dua VM pada PC yang sama berbagi CPU fisik.

**Hasil bervariasi antar-run (terukur).** Plan pemanasan yang sama menghasilkan 162, 153, dan 126 detik. Penyebabnya
belum diketahui; dapat berupa beban PC, jaringan, atau kondisi k3s.

## 6. Perbandingan dengan simulasi

| Aspek | Simulasi (CloudSim Plus) | Real world (k3s) |
|---|---|---|
| Topologi | 3 DC, 5 host/DC, 2 VM/host | 1 DC, 2 host fisik, 4 VM |
| Eksekusi task | Dihitung oleh model | Pod Kubernetes, CPU nyata |
| Overhead per task | Tidak ada | Ada (pod start, penjadwalan) |
| CPU | Setiap VM punya CPU sendiri | VM pada PC yang sama berbagi CPU fisik |
| Jaringan | Tidak dimodelkan | Antar-PC lewat Tailscale (sebagian relay) |
| Hasil | Deterministik | Bervariasi antar-run |

## 7. Keterbatasan

- Beban kerja sintetis (loop CPU), bukan aplikasi nyata; panjang task GoCJ diskalakan seragam.
- Keputusan Max-Min dihitung sekali di depan oleh planner, lalu dijalankan oleh `run_plan.py`. Scheduler tidak
  berjalan sebagai komponen di dalam Kubernetes.
- Satu run per ukuran (100-1000 task); belum ada pengulangan untuk mengukur variasi antar-run.
- Run pertama 400 task terganggu karena skrip pemulai terpanggil tiga kali sehingga tiga batch berjalan bersamaan
  (2767 detik, selisih 130,6%). Hasil itu dibuang dan 400 task diulang dengan satu batch.
- Pada 1000 task selisih naik ke 69,1% dan throughput turun; seluruh Job disimpan sampai run selesai dan server k3s
  (2 vCPU, 2 GB) ikut menjalankan task, sehingga diduga kewalahan (belum diukur).
- Resolusi waktu pengukuran 1 detik.
- Cluster mandiri pada perangkat sendiri, bukan cloud publik (kredit tidak tersedia).

## 8. Saran

- Mengukur biaya start pod secara langsung (selisih waktu pembuatan Job dan awal eksekusi) untuk menguji dugaan
  overhead per task.
- Memindahkan server k3s ke node khusus atau menjalankan `run_plan.py` di luar node worker, lalu membandingkan
  utilisasi PC 1 dan PC 2.
- Mengulang tiap ukuran beberapa kali untuk menghitung variasi antar-run.
- Memasukkan overhead per task ke model simulasi agar prediksi lebih dekat ke kenyataan.
- Menjalankan scheduler di dalam cluster pada server baru yang akan disediakan untuk project berikutnya.

## 9. Reproduksi

Lihat `README.md` di folder ini: langkah pemasangan cluster, kalibrasi, pembuatan plan, dan eksekusi.
Data mentah: `hasil_ringkas.txt`, `hasil_ringkas_2.txt`, `nodes.csv`, `batch_*.csv`, `plan_*.csv`.
