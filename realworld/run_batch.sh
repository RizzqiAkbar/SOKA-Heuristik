#!/bin/bash
# Jalankan beberapa plan Max-Min berurutan di cluster. Hasil tiap plan -> hasil_<N>.txt
cd /home/ubuntu
siap=$(kubectl get nodes --no-headers | grep -c ' Ready')
if [ "$siap" -ne 4 ]; then echo "Hanya $siap node Ready, batal."; exit 1; fi
rm -f hasil_ringkas.txt
for n in 100 200 300 500; do
  echo "[$(date +%H:%M:%S)] mulai $n task"
  python3 run_plan.py batch_$n.csv nodes.csv > hasil_$n.txt 2>&1
  echo "[$(date +%H:%M:%S)] selesai $n task (kode $?)"
  { echo "##### $n task #####"; sed -n '/=== HASIL/,$p' hasil_$n.txt; echo; } >> hasil_ringkas.txt
done
echo "[$(date +%H:%M:%S)] SEMUA SELESAI"
