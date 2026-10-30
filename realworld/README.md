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
| Pemanasan (task rata-rata sekitar 3 detik) | 60,0 detik | 162,0 detik | 170,0% |
| `plan_600.csv` | 600,0 detik | 754,0 detik | 25,7% |

Pembagian task pada `plan_600.csv`: vm-a1 32, vm-a2 16, vm-b1 33, vm-b2 19 (node 2 vCPU mendapat sekitar dua kali
lipat node 1 vCPU). Selisih turun dari 170% menjadi 25,7% saat task dibuat lebih panjang, yang konsisten dengan
biaya tetap per task (membuat Job, menjadwalkan pod, memulai container) sebagai penyebab utama. Simulasi tidak
memodelkan biaya itu. Penyebab lain yang mungkin, belum diukur terpisah: k3s server memakai CPU di vm-a1, dan dua VM
berbagi CPU PC yang sama.

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
