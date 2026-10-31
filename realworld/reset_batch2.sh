#!/bin/bash
# Menghentikan semua batch2 yang berjalan, membersihkan cluster, lalu memulai batch2 satu kali.
# Pola "[r]un_..." agar pkill tidak mencocokkan dirinya sendiri.
cd /home/ubuntu

echo "proses sebelum dibersihkan:"
pgrep -af '[r]un_batch2|[r]un_plan.py' || echo "(tidak ada)"

pkill -f '[r]un_batch2.sh'
pkill -f '[r]un_plan.py'
sleep 3

kubectl delete jobs --all --wait=false > /dev/null 2>&1
for i in $(seq 1 60); do
  [ "$(kubectl get pods --no-headers 2>/dev/null | wc -l)" -eq 0 ] && break
  sleep 5
done
echo "pod tersisa: $(kubectl get pods --no-headers 2>/dev/null | wc -l)"
echo "node Ready : $(kubectl get nodes --no-headers 2>/dev/null | grep -c ' Ready')"

# simpan hasil lama yang tercemar (jangan dipakai), lalu mulai dari awal
[ -f hasil_ringkas_2.txt ] && mv hasil_ringkas_2.txt hasil_ringkas_2_TERCEMAR.txt
rm -f hasil_400.txt hasil_600.txt hasil_700.txt hasil_800.txt hasil_900.txt hasil_1000.txt
sleep 30

bash /home/ubuntu/start_batch2.sh
