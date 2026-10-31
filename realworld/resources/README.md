# Resources

Bukti pengujian real world (screenshot terminal).

## screenshot/pc1 (PC 1, Windows Pro, driver Hyper-V: vm-a1, vm-a2)

| File | Isi |
|---|---|
| `01_pemulihan_cluster_dan_pemanasan_153s.png` | VM dinyalakan kembali, `tailscale status`, node `Ready`, lalu run pemanasan 100 task (153 detik) |
| `02_pemanasan_126s.png` | Run pemanasan 100 task yang lain (126 detik) |
| `03_spesifikasi_vm_a1_vm_a2.png` | `multipass info`: vm-a1 2 vCPU, vm-a2 1 vCPU |
| `04_nodes_csv_hasil_kalibrasi.png` | `nodes.csv`: vCPU dan kecepatan (iterasi/detik) tiap VM |
| `05_kubectl_get_nodes.png` | Empat node `Ready` |
| `06_kubectl_get_nodes_wide_setelah_batch.png` | Empat node `Ready` dengan IP Tailscale, umur 38 jam |
| `07_tailscale_status.png` | Empat VM satu tailnet; vm-b1 dan vm-b2 lewat relay |
| `08_pod_task_selesai_per_node.png` | `kubectl get pods -o wide`: pod task `Completed` tersebar di empat node |
| `09_pod_kosong_setelah_batch.png` | Tidak ada pod tersisa setelah batch |
| `10_batch2_log_400_sampai_1000.png` | Log batch: jam mulai dan selesai 400-1000 task, semua `kode 0` |
| `hasil_<N>_task.png` | Hasil run N task (100-1000): prediksi, aktual, throughput, task dan utilisasi per node |

## screenshot/pc2 (PC 2, Windows Home, driver HCS: vm-b1, vm-b2)

| File | Isi |
|---|---|
| `01_multipass_list_vm_b1_vm_b2.png` | Kedua VM `Running` dengan IP Tailscale |
| `02_spesifikasi_vm_b1_vm_b2.png` | `multipass info`: vm-b1 2 vCPU, vm-b2 1 vCPU |
| `03_k3s_agent_vm_b1.png` | `k3s-agent` aktif di vm-b1 |
| `04_k3s_agent_vm_b2.png` | `k3s-agent` aktif di vm-b2 |
| `05_driver_multipass_hcs.png` | Driver Multipass = `hcs` |

Grafik ada di folder `../grafik/`.
