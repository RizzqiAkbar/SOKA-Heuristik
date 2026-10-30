# Max-Min di cluster nyata (2 laptop x 2 VM, k3s + Tailscale)

Alur: Max-Min (Java) menghasilkan plan -> `run_plan.py` menjalankan tiap task sebagai
Kubernetes Job di node pilihan Max-Min -> ukur makespan nyata vs prediksi.

Susunan (nama VM = nama node di Kubernetes):

| Laptop | VM | vCPU | RAM | Peran |
|---|---|---|---|---|
| A (kamu) | vm-a1 | 2 | 2 GB | k3s server + worker |
| A (kamu) | vm-a2 | 1 | 1,5 GB | worker |
| B (temanmu) | vm-b1 | 2 | 2 GB | worker |
| B (temanmu) | vm-b2 | 1 | 1,5 GB | worker |

## Pembagian tugas
- **Kamu**: akun Tailscale, VM di laptop A, k3s server, kalibrasi, plan, run.
- **Temanmu**: pasang Multipass, buat 2 VM, jalankan 1 perintah per VM (Langkah 3). Selesai.
  Dia tidak perlu paham Kubernetes. Dia hanya perlu laptop menyala dan online saat demo.

## Langkah 0 - Siapkan file di Windows (di WSL)
Multipass jalan di Windows, jadi salin file ke folder Windows:

    mkdir -p /mnt/c/maxmin && cp realworld/*.py realworld/*.sh /mnt/c/maxmin/

Semua perintah `multipass ...` di bawah dijalankan di **PowerShell Windows**, di folder `C:\maxmin`.

## Langkah 1 - Tailscale key (kamu)
Buat akun di tailscale.com -> Settings -> Keys -> **Generate auth key**, centang **Reusable**.
Kirim key itu ke temanmu (satu key dipakai 4 VM).

## Langkah 2 - Laptop A (kamu), PowerShell
    winget install Canonical.Multipass
(Windows Home saja: `multipass set local.driver=virtualbox`)

    cd C:\maxmin
    multipass launch 24.04 --name vm-a1 --cpus 2 --memory 2G --disk 10G
    multipass launch 24.04 --name vm-a2 --cpus 1 --memory 1500M --disk 10G
    multipass transfer vm_setup.sh vm-a1:/home/ubuntu/
    multipass transfer vm_setup.sh vm-a2:/home/ubuntu/

Server dulu (ganti KEY):

    multipass exec vm-a1 -- sudo bash /home/ubuntu/vm_setup.sh server vm-a1 KEY

Di akhir tercetak **IP server** dan **Token**. Kirim keduanya ke temanmu. Lalu:

    multipass exec vm-a2 -- sudo bash /home/ubuntu/vm_setup.sh agent vm-a2 KEY IP_SERVER TOKEN

## Langkah 3 - Laptop B (temanmu), PowerShell
Kirim ke dia: file `vm_setup.sh`, KEY, IP_SERVER, TOKEN. Dia menjalankan:

    winget install Canonical.Multipass
    multipass launch 24.04 --name vm-b1 --cpus 2 --memory 2G --disk 10G
    multipass launch 24.04 --name vm-b2 --cpus 1 --memory 1500M --disk 10G
    multipass transfer vm_setup.sh vm-b1:/home/ubuntu/
    multipass transfer vm_setup.sh vm-b2:/home/ubuntu/
    multipass exec vm-b1 -- sudo bash /home/ubuntu/vm_setup.sh agent vm-b1 KEY IP_SERVER TOKEN
    multipass exec vm-b2 -- sudo bash /home/ubuntu/vm_setup.sh agent vm-b2 KEY IP_SERVER TOKEN

## Langkah 4 - Cek cluster (kamu)
    multipass exec vm-a1 -- kubectl get nodes
Harus muncul 4 node `Ready` (vm-a1, vm-a2, vm-b1, vm-b2). Kalau belum, tunggu 1-2 menit.
Kalau ada yang tidak muncul: `multipass exec vm-X -- sudo journalctl -u k3s-agent -n 30`.

## Langkah 5 - Kalibrasi kecepatan node (kamu)
    multipass transfer calibrate.py vm-a1:/home/ubuntu/
    multipass exec vm-a1 -- python3 /home/ubuntu/calibrate.py /home/ubuntu/nodes.csv
    multipass transfer vm-a1:/home/ubuntu/nodes.csv .
Ini mengukur kecepatan tiap node DI DALAM container (sama seperti task asli) dan otomatis
mendeteksi jumlah vCPU. Semua node diukur serentak. Butuh beberapa menit (tarik image pertama kali).
Lalu di WSL: `cp /mnt/c/maxmin/nodes.csv realworld/nodes.csv`

## Langkah 6 - Buat plan Max-Min (WSL, folder project)
Dataset hanya ada untuk 100, 150, 200, ... 1000 task.

    mvn -q compile
    java -cp target/classes:$(mvn -q dependency:build-classpath -Dmdep.outputFile=/dev/stdout) org.example.RealWorldPlanner 100 realworld/nodes.csv 300 realworld/plan.csv

Argumen: jumlah task, nodes.csv, **prediksi makespan (detik)**, plan.csv.
Pakai prediksi sekitar 300 detik atau lebih. Prediksi yang terlalu kecil membuat task sangat pendek,
dan overhead start pod (sekitar 1-2 detik per task) jadi dominan.

## Langkah 7 - Jalankan (kamu)
    cp realworld/plan.csv /mnt/c/maxmin/
Di PowerShell:

    cd C:\maxmin
    multipass transfer plan.csv nodes.csv run_plan.py vm-a1:/home/ubuntu/
    multipass exec vm-a1 -- python3 /home/ubuntu/run_plan.py /home/ubuntu/plan.csv /home/ubuntu/nodes.csv

Hasil: prediksi vs makespan nyata, throughput, jumlah task dan utilisasi tiap node.
Lakukan satu kali run pemanasan lebih dulu (plan 100 task, prediksi 60) supaya image sudah ter-cache.

## Troubleshooting
- Node tidak Ready: pastikan Tailscale aktif di VM itu (`tailscale status`) dan laptop temanmu online.
- Job `ImagePullBackOff`: VM tidak punya internet; cek `multipass exec vm-X -- ping -c2 1.1.1.1`.
- Selisih prediksi vs aktual besar itu wajar: Kubernetes menambah overhead start pod, dua VM berbagi
  CPU laptop yang sama, dan k3s server ikut memakai CPU vm-a1. Itu bahan penjelasan "simulasi vs dunia nyata".
