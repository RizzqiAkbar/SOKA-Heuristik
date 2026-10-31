#!/bin/bash
# Memulai run_batch2.sh di latar belakang; log -> /home/ubuntu/batch2.log
# Menolak jalan bila batch sebelumnya masih aktif (dua batch sekaligus saling menghapus Job dan merusak hasil).
if pgrep -f run_batch2.sh > /dev/null; then
  echo "SUDAH BERJALAN, tidak dimulai lagi. Lihat: cat /home/ubuntu/batch2.log"
  exit 1
fi
setsid nohup bash /home/ubuntu/run_batch2.sh > /home/ubuntu/batch2.log 2>&1 < /dev/null &
sleep 3
cat /home/ubuntu/batch2.log
