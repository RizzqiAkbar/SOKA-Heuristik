#!/bin/bash
# Memulai run_batch.sh di latar belakang; log -> /home/ubuntu/batch.log
setsid nohup bash /home/ubuntu/run_batch.sh > /home/ubuntu/batch.log 2>&1 < /dev/null &
sleep 3
cat /home/ubuntu/batch.log
