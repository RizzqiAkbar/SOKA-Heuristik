# Max-Min di Cluster Kubernetes Nyata (2 PC x 2 VM, k3s + Tailscale)

Alur: Max-Min (Java) menghasilkan plan -> `run_plan.py` menjalankan tiap task sebagai
Kubernetes Job di node yang dipilih Max-Min -> makespan nyata diukur dan dibandingkan dengan prediksi.

## Susunan

Nama VM sama dengan nama node di Kubernetes.

| PC | VM | vCPU | RAM | Peran |
|---|---|---|---|---|
| PC 1 | vm-a1 | 2 | 2 GB | k3s server + worker |
| PC 1 | vm-a2 | 1 | 1,5 GB | worker |
| PC 2 | vm-b1 | 2 | 2 GB | worker |
| PC 2 | vm-b2 | 1 | 1,5 GB | worker |

Pemetaan ke syarat: 1 datacenter (1 cluster k3s), 2 host (PC 1 dan PC 2), 2 VM per host,
heuristik Max-Min. Kedua PC berada di jaringan WiFi berbeda dan dihubungkan lewat Tailscale.

## Pembagian tugas

- **PC 1**: akun Tailscale, VM, k3s server, kalibrasi, pembuatan plan, eksekusi.
- **PC 2**: Multipass, 2 VM, satu perintah setup per VM (Langkah 3). PC 2 harus menyala dan online selama eksekusi.

Semua perintah `multipass ...` dijalankan di **PowerShell Windows**. Perintah Java dijalankan di WSL, di folder repo.

## Langkah 0 - Siapkan file di Windows (PC 1, WSL)

Multipass berjalan di Windows, jadi salin file ke folder Windows:

    mkdir -p /mnt/c/maxmin && cp realworld/*.py realworld/*.sh /mnt/c/maxmin/

## Langkah 1 - Tailscale auth key (PC 1)

tailscale.com -> Settings -> Keys -> **Generate auth key**, centang **Reusable**, kedaluwarsa 7 hari atau lebih.
Satu key dipakai untuk 4 VM.

Penting: semua VM harus login ke **akun Tailscale yang sama**. Key dari akun lain membuat VM berada di
jaringan terpisah (gejala: `tailscale ping` memberi `no matching peer`, node k3s tidak pernah bergabung).
Cek dengan `tailscale status`; semua VM harus menampilkan akun yang sama.

## Langkah 2 - PC 1 (PowerShell)

    winget install Canonical.Multipass

    cd C:\maxmin
    multipass launch 24.04 --name vm-a1 --cpus 2 --memory 2G --disk 10G
    multipass launch 24.04 --name vm-a2 --cpus 1 --memory 1500M --disk 10G
    multipass transfer vm_setup.sh vm-a1:/home/ubuntu/
    multipass transfer vm_setup.sh vm-a2:/home/ubuntu/

Server dahulu (ganti KEY):

    multipass exec vm-a1 -- sudo bash /home/ubuntu/vm_setup.sh server vm-a1 KEY

Di akhir tercetak **IP server** dan **Token**. Keduanya dipakai di PC 2 dan di vm-a2:

    multipass exec vm-a2 -- sudo bash /home/ubuntu/vm_setup.sh agent vm-a2 KEY IP_SERVER TOKEN

Token dapat dibaca ulang kapan saja:

    multipass exec vm-a1 -- sudo cat /var/lib/rancher/k3s/server/node-token

## Langkah 3 - PC 2 (PowerShell)

File yang dibutuhkan: `vm_setup.sh`, KEY, IP_SERVER, TOKEN.

    winget install Canonical.Multipass

**Windows Home:** gunakan driver `hcs` (berbasis Hyper-V). Pada pengujian ini, driver VirtualBox membuat VM
dengan 2 vCPU berhenti di tahap firmware (UEFI) saat Windows hypervisor aktif.

    multipass set local.driver=hcs

Lalu:

    $mp = "C:\Program Files\Multipass\bin\multipass.exe"
    & $mp launch 24.04 --name vm-b1 --cpus 2 --memory 2G --disk 10G --timeout 900
    & $mp launch 24.04 --name vm-b2 --cpus 1 --memory 1500M --disk 10G --timeout 900
    & $mp transfer vm_setup.sh vm-b1:/home/ubuntu/
    & $mp transfer vm_setup.sh vm-b2:/home/ubuntu/
    & $mp exec vm-b1 -- sudo bash /home/ubuntu/vm_setup.sh agent vm-b1 KEY IP_SERVER TOKEN
    & $mp exec vm-b2 -- sudo bash /home/ubuntu/vm_setup.sh agent vm-b2 KEY IP_SERVER TOKEN

Perintah setup dapat berhenti beberapa menit di baris `systemd: Starting k3s-agent` sampai node
terdaftar ke server. Itu normal.

## Langkah 4 - Cek cluster (PC 1)

    multipass exec vm-a1 -- kubectl get nodes

Harus muncul 4 node `Ready`: vm-a1, vm-a2, vm-b1, vm-b2 (1-2 menit setelah setup).
Jika ada yang tidak muncul: `multipass exec vm-X -- sudo journalctl -u k3s-agent -n 30 --no-pager`
dan `multipass exec vm-X -- tailscale status`.

## Langkah 5 - Kalibrasi kecepatan node (PC 1)

    multipass transfer calibrate.py vm-a1:/home/ubuntu/
    multipass exec vm-a1 -- python3 /home/ubuntu/calibrate.py /home/ubuntu/nodes.csv
    multipass transfer vm-a1:/home/ubuntu/nodes.csv .

Kecepatan setiap node diukur di dalam container (sama seperti task asli), semua node serentak, dan jumlah vCPU
terdeteksi otomatis. Butuh beberapa menit (image ditarik pertama kali). Pesan `cannot set permissions` dari
`multipass transfer` boleh diabaikan jika file tetap tersalin.

Lalu di WSL: `cp /mnt/c/maxmin/nodes.csv realworld/nodes.csv`

## Langkah 6 - Buat plan Max-Min (WSL, folder repo)

Dataset GoCJ tersedia untuk 100, 150, 200, ..., 1000 task.

    mvn -q compile
    java -cp target/classes:$(mvn -q dependency:build-classpath -Dmdep.outputFile=/dev/stdout) org.example.RealWorldPlanner 100 realworld/nodes.csv 600 realworld/plan_600.csv

Argumen: jumlah task, nodes.csv, **prediksi makespan (detik)**, plan.csv.

Panjang task diambil dari GoCJ lalu dikalikan satu faktor yang sama agar prediksi simulasi jatuh di angka target.
Faktor seragam tidak mengubah keputusan Max-Min: pembagian task ke node sama dengan di simulasi.

Pilih target yang cukup besar. Setiap task adalah satu Kubernetes Job dengan overhead start pod sekitar beberapa
detik, sehingga task yang terlalu pendek membuat hasil nyata jauh dari prediksi. Plan yang tersedia di folder ini:

| File | Task | Prediksi |
|---|---|---|
| `plan_300.csv` | 100 | 300 detik |
| `plan_600.csv` | 100 | 600 detik |

## Langkah 7 - Jalankan (PC 1)

    cp realworld/plan_600.csv /mnt/c/maxmin/

Di PowerShell:

    cd C:\maxmin
    multipass transfer plan_600.csv nodes.csv run_plan.py vm-a1:/home/ubuntu/
    multipass exec vm-a1 -- python3 /home/ubuntu/run_plan.py /home/ubuntu/plan_600.csv /home/ubuntu/nodes.csv

Hasil: prediksi vs makespan nyata, throughput, serta jumlah task dan utilisasi tiap node.

Task pertama adalah yang terpanjang (Max-Min menjalankan task terbesar lebih dulu), jadi penghitung
`selesai X/100` baru naik setelah beberapa menit pada `plan_600.csv`. Itu normal.

Jalankan satu kali pemanasan lebih dulu agar image ter-cache di semua node (plan 100 task, prediksi 60 detik):

    java -cp target/classes:$(mvn -q dependency:build-classpath -Dmdep.outputFile=/dev/stdout) org.example.RealWorldPlanner 100 realworld/nodes.csv 60 realworld/plan_warmup.csv

## Hasil pengujian (100 task GoCJ, 4 node)

| Plan | Prediksi | Aktual | Selisih |
|---|---|---|---|
| Pemanasan (task rata-rata sekitar 3,6 detik) | 60,0 detik | 162,0 detik | 170,0% |
| `plan_600.csv` | 600,0 detik | 754,0 detik | 25,7% |

Pembagian task pada `plan_600.csv`: vm-a1 32, vm-a2 16, vm-b1 33, vm-b2 19 (node 2 vCPU mendapat sekitar dua kali
lipat node 1 vCPU). Selisih turun dari 170% menjadi 25,7% saat task dibuat lebih panjang, yang konsisten dengan
biaya tetap per task (membuat Job, menjadwalkan pod, memulai container) sebagai penyebab utama. Simulasi tidak
memodelkan biaya itu. Penyebab lain yang mungkin, belum diukur terpisah: k3s server memakai CPU di vm-a1, dan dua VM
berbagi CPU PC yang sama.

## Hasil batch 100-1000 task (target = 3 x jumlah task)

Batch pertama (100, 200, 300, 500 task) dijalankan dengan `run_batch.sh` (dimulai lewat `start_batch.sh`);
keluarannya di `hasil_ringkas.txt`. Batch kedua (400, 600, 700, 800, 900, 1000 task) dijalankan dengan
`run_batch2.sh` (dimulai lewat `start_batch2.sh`); keluarannya di `hasil_ringkas_2.txt`. Plan-nya `batch_<N>.csv`.
Semua run berstatus `kode 0` (selesai, tidak kena batas waktu). Satu run per ukuran.

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

Utilisasi dan jumlah task per node:

| Task | vm-a1 (2 vCPU) | vm-a2 (1 vCPU) | vm-b1 (2 vCPU) | vm-b2 (1 vCPU) |
|---|---|---|---|---|
| 400 | 126 task, 95,0% | 69 task, 94,3% | 132 task, 56,9% | 73 task, 63,8% |
| 600 | 188 task, 94,5% | 105 task, 94,0% | 198 task, 55,4% | 109 task, 61,3% |
| 700 | 219 task, 93,6% | 121 task, 93,2% | 233 task, 61,6% | 127 task, 68,9% |
| 800 | 253 task, 94,4% | 139 task, 92,7% | 262 task, 57,0% | 146 task, 63,2% |
| 900 | 284 task, 93,6% | 156 task, 92,9% | 296 task, 57,3% | 164 task, 64,2% |
| 1000 | 314 task, 93,5% | 173 task, 89,6% | 330 task, 47,7% | 183 task, 53,0% |

(Baris 100, 200, 300, 500 task ada di `hasil_ringkas.txt`.)

Yang terukur:
- Pembagian task ke node proporsional terhadap vCPU di semua ukuran (node 2 vCPU mendapat sekitar dua kali node
  1 vCPU).
- Selisih aktual terhadap prediksi 33-54% untuk 100-900 task. Tidak ada tren naik atau turun yang jelas setelah
  200 task; naik-turunnya (misalnya 33,0% pada 700 dan 46,0% pada 600) kemungkinan variasi antar-run, karena tiap
  ukuran hanya satu run dan plan pemanasan yang sama pernah menghasilkan 162, 153, dan 126 detik.
- Throughput sekitar 0,23-0,25 task/detik untuk 300-900 task.
- 1000 task paling lambat: selisih 69,1%, throughput 0,197 task/detik, dan utilisasi semua node turun (vm-a2 89,6%;
  vm-b1 47,7%; vm-b2 53,0%). Penyebabnya belum diukur. Dugaan: `run_plan.py` menyimpan 1000 Job dan meminta daftar
  Job tiap detik di vm-a1 (2 vCPU, 2 GB, yang juga menjadi k3s server), sehingga pengendali itu sendiri melambat.

Utilisasi tidak merata antar-PC pada semua ukuran: vm-a1 dan vm-a2 (PC 1) 93-97% untuk 100-900 task, sedangkan
vm-b1 dan vm-b2 (PC 2) 55-72%. Terukur: `tailscale status` menunjukkan vm-b1 dan vm-b2 terhubung ke PC 1 lewat relay
Tailscale (`relay "sin"`), sedangkan vm-a2 terhubung langsung. Dugaan (belum diuji terpisah): k3s server berada di
PC 1, sehingga laporan status task dari PC 2 tertunda oleh relay, dan task berikutnya baru dibuat setelah
penyelesaian task sebelumnya terdeteksi, sehingga node PC 2 punya jeda kosong antar task. Beban k3s server dan
`run_plan.py` di vm-a1 juga dapat memperlambat PC 1.

Catatan: run pertama 400 task terganggu karena `start_batch2.sh` terpanggil tiga kali sehingga tiga batch berjalan
bersamaan (hasil 2767 detik, selisih 130,6%). Hasil itu dibuang dan 400 task diulang dengan satu batch (tabel di
atas). `start_batch2.sh` kini menolak berjalan bila batch masih aktif.

## Grafik

    python3 buat_grafik_realworld.py

Membaca `hasil_ringkas.txt` dan `hasil_ringkas_2.txt`, lalu menulis empat PNG ke folder `grafik/`:
`1_prediksi_vs_aktual.png`, `2_utilisasi_node.png`, `3_selisih_vs_jumlah_task.png`, dan
`4_selisih_vs_panjang_task.png` (100 task dengan panjang task berbeda). Panduan mengubah topologi (DC, host, VM) ada
di `PANDUAN_UBAH_TOPOLOGI.md`.

## Screenshot bukti

Folder `resources/` berisi screenshot pengujian dari PC 1 dan PC 2; daftar isinya di `resources/README.md`.

## Setelah PC dimatikan atau di-restart

VM tidak menyala otomatis. Di tiap PC (PowerShell):

    multipass start --all

Tunggu 1-3 menit, lalu cek `kubectl get nodes` (Langkah 4). Tailscale dan k3s menyala sendiri di dalam VM.
Selama eksekusi, PC jangan masuk mode tidur dan tetap online.

## Pembersihan setelah selesai

- Cabut auth key di tailscale.com -> Settings -> Keys.
- Hapus VM di tiap PC: `multipass delete --all --purge`.

## Troubleshooting

- Node tidak Ready: pastikan Tailscale aktif di VM itu (`tailscale status`) dan PC lain online.
- `tailscale ping` memberi `no matching peer`: VM berada di akun/jaringan Tailscale lain; login ulang
  dengan key dari akun yang sama (`sudo tailscale logout`, lalu jalankan ulang `vm_setup.sh`).
- `invalid key`: key kedaluwarsa atau salah; buat key baru (Reusable).
- Job `ImagePullBackOff`: VM tidak punya internet; cek `multipass exec vm-X -- ping -c2 1.1.1.1`.
- `cannot connect to the multipass socket` setelah mengganti driver: tunggu sebentar, atau PowerShell
  Administrator: `Restart-Service Multipass`.
