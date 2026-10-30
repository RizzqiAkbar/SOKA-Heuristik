#!/usr/bin/env python3
"""
Jalankan plan Max-Min ke cluster Kubernetes dan ukur makespan sebenarnya.

Pakai: python3 run_plan.py plan.csv nodes.csv

Satu task = satu Kubernetes Job yang dipaksa jalan di node pilihan Max-Min
(nodeSelector) dan mengerjakan loop CPU sebanyak `iterations`.
Node dengan N vCPU menjalankan maksimal N task sekaligus, sisanya antre sesuai
urutan Max-Min (sama seperti CloudletSchedulerSpaceShared di simulasi).
"""
import csv
import json
import subprocess
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

RUN = "run%d" % time.time()


def kubectl(*args, stdin=None):
    r = subprocess.run(["kubectl", *args], input=stdin, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("kubectl gagal: " + r.stderr)
    return r.stdout


def start_job(seq, node, iterations):
    name = "task-%s-%s" % (RUN, seq)
    job = {
        "apiVersion": "batch/v1", "kind": "Job",
        "metadata": {"name": name, "labels": {"run": RUN}},
        "spec": {"backoffLimit": 0, "template": {"spec": {
            "restartPolicy": "Never",
            "nodeSelector": {"kubernetes.io/hostname": node},   # tempel ke node pilihan Max-Min
            "containers": [{
                "name": "w", "image": "python:3.12-alpine",
                "command": ["python", "-c", "import sys\nfor _ in range(int(sys.argv[1])): pass", iterations],
            }],
        }}},
    }
    kubectl("create", "-f", "-", stdin=json.dumps(job))
    return name


def ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


lines = open(sys.argv[1]).read().splitlines()
predicted = float(lines[0].split("=")[1])
plan = list(csv.DictReader(lines[1:]))
vcpu = {r["node"]: int(r["pes"]) for r in csv.DictReader(open(sys.argv[2]))}

queue = defaultdict(deque)                  # antrean per node, urut keputusan Max-Min
for t in plan:
    queue[t["node"]].append(t)
running = defaultdict(set)                  # job yang sedang jalan per node
node_of, finished = {}, {}

while len(finished) < len(plan):
    for node in vcpu:                       # isi slot kosong (1 vCPU = 1 slot)
        while queue[node] and len(running[node]) < vcpu[node]:
            t = queue[node].popleft()
            name = start_job(t["seq"], node, t["iterations"])
            running[node].add(name)
            node_of[name] = node
    time.sleep(1)
    jobs = json.loads(kubectl("get", "jobs", "-l", "run=" + RUN, "-o", "json"))["items"]
    for j in jobs:
        name, st = j["metadata"]["name"], j["status"]
        if st.get("failed"):
            sys.exit("Job %s gagal, cek: kubectl describe job %s" % (name, name))
        if st.get("succeeded") and name not in finished:
            finished[name] = (ts(j["metadata"]["creationTimestamp"]), ts(st["startTime"]), ts(st["completionTime"]))
            running[node_of[name]].discard(name)
    print("\rselesai %d/%d" % (len(finished), len(plan)), end="", flush=True)

kubectl("delete", "jobs", "-l", "run=" + RUN, "--wait=false")

makespan = max(f[2] for f in finished.values()) - min(f[0] for f in finished.values())
print("\n\n=== HASIL DUNIA NYATA (Max-Min, %d task) ===" % len(plan))
print("Prediksi makespan : %.1f detik" % predicted)
print("Makespan aktual   : %.1f detik (selisih %.1f%%)" % (makespan, abs(makespan - predicted) / predicted * 100))
print("Throughput        : %.3f task/detik\n" % (len(plan) / makespan))
print("%-10s %5s %6s %9s" % ("Node", "vCPU", "Task", "Util(%)"))
for node in vcpu:
    mine = [finished[n] for n in finished if node_of[n] == node]
    busy = sum(f[2] - f[1] for f in mine)
    print("%-10s %5d %6d %9.1f" % (node, vcpu[node], len(mine), 100 * busy / (vcpu[node] * makespan)))
