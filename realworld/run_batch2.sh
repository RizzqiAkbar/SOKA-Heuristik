#!/bin/bash
# Batch lanjutan: jalankan plan Max-Min berurutan. Hasil tiap plan -> hasil_<N>.txt, ringkasan -> hasil_ringkas_2.txt
cd /home/ubuntu

siap() { kubectl get nodes --no-headers 2>/dev/null | grep -c ' Ready'; }

for n in 400 600 700 800 900 1000; do
  # tunggu empat node Ready (maksimal 10 menit), kalau tidak, berhenti
  for i in $(seq 1 60); do [ "$(siap)" -eq 4 ] && break; sleep 10; done
  if [ "$(siap)" -ne 4 ]; then echo "[$(date +%H:%M:%S)] node tidak lengkap, batal sebelum $n task"; exit 1; fi

  echo "[$(date +%H:%M:%S)] mulai $n task"
  timeout $((9 * n)) python3 run_plan.py batch_$n.csv nodes.csv > hasil_$n.txt 2>&1
  status=$?
  echo "[$(date +%H:%M:%S)] selesai $n task (kode $status; 124 = melewati batas waktu)"
  { echo "##### $n task (kode $status) #####"; sed -n '/=== HASIL/,$p' hasil_$n.txt; echo; } >> hasil_ringkas_2.txt

  # bersihkan sisa Job dan tunggu semua pod hilang sebelum run berikutnya
  kubectl delete jobs --all --wait=false > /dev/null 2>&1
  for i in $(seq 1 60); do [ "$(kubectl get pods --no-headers 2>/dev/null | wc -l)" -eq 0 ] && break; sleep 5; done
  sleep 30
done
echo "[$(date +%H:%M:%S)] SEMUA SELESAI"
