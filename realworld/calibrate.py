#!/usr/bin/env python3
"""
Ukur kecepatan tiap node DI DALAM container (sama seperti task asli) -> nodes.csv.
Semua node diukur SERENTAK, 1 proses per vCPU, supaya hasilnya sudah
memperhitungkan CPU laptop yang dipakai bersama oleh 2 VM.

Pakai: python3 calibrate.py [nodes.csv]
"""
import csv
import json
import subprocess
import sys

ITERS = 30_000_000
LOOP = "import time\nt=time.time()\nfor _ in range(%d): pass\nprint(time.time()-t)" % ITERS


def kubectl(*args, stdin=None):
    r = subprocess.run(["kubectl", *args], input=stdin, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("kubectl gagal: " + r.stderr)
    return r.stdout


def job(name, node, label):
    return json.dumps({
        "apiVersion": "batch/v1", "kind": "Job",
        "metadata": {"name": name, "labels": {"calib": label}},
        "spec": {"backoffLimit": 0, "template": {"spec": {
            "restartPolicy": "Never",
            "nodeSelector": {"kubernetes.io/hostname": node},
            "containers": [{"name": "w", "image": "python:3.12-alpine", "command": ["python", "-c", LOOP]}],
        }}},
    })


nodes = {n["metadata"]["name"]: int(n["status"]["capacity"]["cpu"])
         for n in json.loads(kubectl("get", "nodes", "-o", "json"))["items"]}
rates = {}
for rnd in ("pemanasan", "ukur"):          # putaran 1 menarik image, putaran 2 dipakai
    print("Putaran %s ..." % rnd)
    names = {}
    for node, cpu in nodes.items():
        for i in range(cpu):
            name = "calib-%s-%s-%d" % (rnd, node, i)
            kubectl("create", "-f", "-", stdin=job(name, node, rnd))
            names[name] = node
    kubectl("wait", "--for=condition=complete", "job", "-l", "calib=" + rnd, "--timeout=900s")
    rates = {n: [] for n in nodes}
    for name, node in names.items():
        rates[node].append(ITERS / float(kubectl("logs", "job/" + name)))
    kubectl("delete", "jobs", "-l", "calib=" + rnd, "--wait=false")

out = sys.argv[1] if len(sys.argv) > 1 else "nodes.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["node", "pes", "iters_per_sec"])
    for node, cpu in nodes.items():
        rate = sum(rates[node]) / len(rates[node])
        w.writerow([node, cpu, int(rate)])
        print("%-10s vCPU=%d  %.1f juta iterasi/detik" % (node, cpu, rate / 1e6))
print("Tersimpan:", out)
