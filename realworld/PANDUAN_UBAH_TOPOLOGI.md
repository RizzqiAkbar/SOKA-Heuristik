# Panduan: di mana DC, host, dan VM didefinisikan, dan cara mengubahnya

Dua bagian terpisah: **simulasi** (CloudSim Plus, Java) dan **real world** (cluster k3s).
Nomor baris mengacu pada `Main.java` saat ini; jika bergeser, cari nama konstanta/fungsinya.

---

## A. Simulasi (CloudSim Plus)

### Lokasi kode

| Item | File | Baris |
|---|---|---|
| **Jumlah DC, host per DC, VM per host** | `Main.java` | 40-42 (`DC_COUNT`, `HOST_PER_DC`, `VM_PER_HOST`) |
| Total host dan VM (dihitung otomatis) | `Main.java` | 43-45 (`HOST_COUNT`, `VM_COUNT`, `VM_PER_DC`) |
| Pembuatan DC dan pembagian host ke DC | `Main.java` | 111-120 (loop `for d < DC_COUNT`, `new DatacenterSimple`) |
| Pembagian VM ke DC (berurutan, `VM_PER_DC` VM per DC) | `Main.java` | 126-127 (`setDatacenterMapper`) |
| Spesifikasi host (PE, MIPS, RAM) | `Main.java` | 182 (`createHosts`): PE 4-16, MIPS/PE 1000-3000, RAM 4-16 GB, acak dengan `HOST_SEED` (baris 62) |
| Spesifikasi VM (MIPS, PE, RAM) | `Main.java` | 198 (`createVms`): MIPS 250-1000, PE 1-4, RAM 512-2048 MB, acak dengan `VM_SEED` (baris 63) |

Path file:
- Project lokal: `src/main/java/org/example/Main.java`
- Repo GitHub (`SOKA-Heuristik`): `src/main/java/Main.java`

Penempatan VM ke host dilakukan otomatis oleh `VmAllocationPolicySimple`, bukan ditulis eksplisit di kode.

### Cara mengubah

Ubah tiga angka di baris 40-42. Contoh:

| Kebutuhan | `DC_COUNT` | `HOST_PER_DC` | `VM_PER_HOST` | Total |
|---|---|---|---|---|
| Konfigurasi sekarang | 3 | 5 | 2 | 3 DC, 15 host, 30 VM |
| Sama dengan real world | 1 | 2 | 2 | 1 DC, 2 host, 4 VM |
| 5 DC | 5 | 5 | 2 | 5 DC, 25 host, 50 VM |

Tidak ada bagian lain yang perlu diubah: total host/VM dan pembagian ke DC dihitung dari tiga konstanta itu.

### Cara menjalankan

Dari folder root project (yang berisi `pom.xml`):

    mvn -q compile exec:java

Waktu: sekitar 15 detik untuk seluruh skenario (19 ukuran dataset x 3 algoritma).
Keluaran ada di folder `output/`:
- `output_terminal.txt` (rincian per VM, termasuk label DC dan host)
- `hasil_metrik_perbandingan.csv` (57 baris: 56 hasil + header)

Peringatan: menjalankan akan **menimpa** `output/hasil_metrik_perbandingan.csv` dan `output/output_terminal.txt`
(di repo kedua file itu ikut tercatat di git). Salin dulu hasil lama jika masih dibutuhkan, dan jangan di-commit
bila konfigurasinya hanya untuk percobaan.

Untuk membuat ulang grafik simulasi: `python3 buat_grafik.py` (membaca `output/hasil_metrik_perbandingan.csv`).

Uji yang sudah dilakukan: 2 DC x 3 host x 2 VM berjalan dan menghasilkan label `DC1`/`DC2` (tanpa `DC3`);
1 DC x 2 host x 2 VM berjalan dan menghasilkan 57 baris CSV.

---

## B. Real world (cluster k3s)

DC, host, dan VM **tidak ditulis sebagai konstanta di kode Java**. Topologinya ditentukan oleh infrastruktur dan
oleh `nodes.csv`.

| Item | Di mana didefinisikan |
|---|---|
| Datacenter | 1 cluster k3s (server di vm-a1). Tidak ada penanda di kode. |
| Host (PC) | PC fisik. Tidak tertulis di kode; terlihat dari nama VM: `vm-a*` di PC 1, `vm-b*` di PC 2. |
| VM | Dibuat dengan `multipass launch ... --cpus N --memory M` (README langkah 2 dan 3). Bergabung ke cluster oleh `vm_setup.sh`. |
| VM yang dipakai Max-Min | `realworld/nodes.csv`: satu baris per VM (`node,pes,iters_per_sec`). Dibuat otomatis oleh `calibrate.py`. |

Kode Java yang membaca `nodes.csv` ada di `RealWorldPlanner.java` (membuat satu VM simulasi per baris).
`run_plan.py` membaca nama node dan jumlah vCPU dari `nodes.csv` yang sama.

### Cara mengubah

**Menambah VM:**
1. Buat VM di PC yang diinginkan: `multipass launch 24.04 --name vm-x --cpus N --memory M --disk 10G`.
2. Pasang agent: `multipass exec vm-x -- sudo bash /home/ubuntu/vm_setup.sh agent vm-x KEY IP_SERVER TOKEN`
   (setelah `vm_setup.sh` dikirim ke VM; lihat README langkah 2-3).
3. Pastikan `kubectl get nodes` menampilkan VM itu `Ready`.
4. Kalibrasi ulang (`calibrate.py`, README langkah 5) agar `nodes.csv` memuat VM baru.
5. Buat plan baru dan jalankan (README langkah 6-7).

**Mengurangi VM:** hapus baris VM itu dari `nodes.csv`, lalu buat plan baru. Node boleh tetap di cluster, karena
`run_plan.py` hanya memakai node yang ada di `nodes.csv`.

**Mengubah jumlah vCPU atau RAM VM:** hapus VM (`multipass delete vm-x --purge`) dan buat ulang dengan nilai baru,
lalu ulangi langkah 2-5 di atas.

**Mengubah jumlah ukuran task / target waktu:** hanya argumen planner (README langkah 6):

    java -cp target/classes:$(mvn -q dependency:build-classpath -Dmdep.outputFile=/dev/stdout) org.example.RealWorldPlanner <jumlah_task> realworld/nodes.csv <target_detik> realworld/plan.csv

`<jumlah_task>` harus salah satu dari 100, 150, ..., 1000 (sesuai file `GoCJ_Dataset_N.txt`).

Uji yang sudah dilakukan: menambah satu baris `vm-c1,2,14000000` ke `nodes.csv` membuat planner langsung membagikan
task ke `vm-c1` juga (26 dari 100 task). Pada cluster sungguhan, node tersebut harus ada dan `Ready`.

### Jika diminta "tampilkan DC, host, dan VM"

- Cluster/VM: `multipass exec vm-a1 -- kubectl get nodes -o wide`
- VM per PC: `multipass list` di tiap PC
- Spesifikasi VM: `multipass info vm-a1 vm-a2` (PC 1) dan `multipass info vm-b1 vm-b2` (PC 2)
- Daftar VM yang dipakai Max-Min beserta kecepatannya: isi `realworld/nodes.csv`
