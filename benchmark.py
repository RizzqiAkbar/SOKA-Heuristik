#!/usr/bin/env python3
"""
Script Benchmark Eksperimen Penjadwalan Heuristik Real-Life (SOKA)
Membandingkan Max-Min, Min-Min, dan FCFS pada container Docker.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error

SCHEDULER_URL = os.getenv("SCHEDULER_URL", "http://localhost:5000")
DATASETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")
DEFAULT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hasil_benchmark.csv")
ALGORITHMS = ["max-min", "min-min", "fcfs"]


def check_scheduler():
    try:
        req = urllib.request.Request(f"{SCHEDULER_URL}/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data.get("status") == "ok"
    except Exception:
        return False


def get_workers():
    try:
        req = urllib.request.Request(f"{SCHEDULER_URL}/workers")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data.get("workers", [])
    except Exception:
        return []


def run_experiment(algorithm, tasks):
    payload = json.dumps({
        "algorithm": algorithm,
        "tasks": tasks
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{SCHEDULER_URL}/run",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=3600) as resp:
        return json.loads(resp.read().decode())


def main():
    parser = argparse.ArgumentParser(description="Benchmark Penjadwalan Heuristik Real-Life")
    parser.add_argument("--dataset", "-d", help="Path atau nama dataset JSON (contoh: 100, GoCJ_Dataset_100, dataset_10.json)")
    parser.add_argument("--gocj", action="store_true", help="Jalankan semua dataset GoCJ (100 - 1000)")
    parser.add_argument("--gocj-step", type=int, default=0, help="Langkah kelipatan GoCJ (contoh: --gocj-step 200)")
    parser.add_argument("--all", action="store_true", help="Jalankan seluruh file dataset yang ada")
    parser.add_argument("--algorithm", "-a", choices=["all", "max-min", "min-min", "fcfs"], default="all")
    parser.add_argument("--output", "-o", default=DEFAULT_CSV, help="File output CSV")
    args = parser.parse_args()

    print("\n" + "=" * 65)
    print("      BENCHMARK PENJADWALAN HEURISTIK REAL-LIFE (SOKA)      ")
    print("=" * 65)

    if not check_scheduler():
        print(f"\n[ERROR] Scheduler tidak dapat dihubungi di {SCHEDULER_URL}")
        print("Pastikan Docker Compose sudah berjalan:")
        print("  cd 'SOKA/real-life'")
        print("  docker compose up -d\n")
        sys.exit(1)

    workers = get_workers()
    online_workers = [w for w in workers if w.get("online")]
    print(f"\n[INFO] Scheduler online di {SCHEDULER_URL}")
    print(f"[INFO] Terdeteksi {len(online_workers)} worker online:")
    for w in online_workers:
        print(f"       - {w['id']} (Host: {w.get('host_id')}, Capacity: {w.get('capacity', 1.0)})")

    # Tentukan dataset yang akan diuji
    datasets_to_run = []
    if args.dataset:
        candidate = args.dataset
        candidates = [
            candidate,
            os.path.join(DATASETS_DIR, candidate),
            os.path.join(DATASETS_DIR, f"{candidate}.json"),
            os.path.join(DATASETS_DIR, f"GoCJ_Dataset_{candidate}.json"),
            os.path.join(DATASETS_DIR, f"dataset_{candidate}.json"),
        ]
        found = None
        for c in candidates:
            if os.path.isfile(c):
                found = c
                break
        if found:
            datasets_to_run.append(found)
        else:
            print(f"[ERROR] File dataset '{args.dataset}' tidak ditemukan.")
            sys.exit(1)
    elif args.gocj or args.gocj_step > 0:
        gocj_files = []
        if os.path.isdir(DATASETS_DIR):
            import re
            for file in os.listdir(DATASETS_DIR):
                m = re.match(r"GoCJ_Dataset_(\d+)\.json", file)
                if m:
                    gocj_files.append((int(m.group(1)), os.path.join(DATASETS_DIR, file)))
            gocj_files.sort(key=lambda x: x[0])
            if args.gocj_step > 0:
                selected = [f for n, f in gocj_files if (n - 100) % args.gocj_step == 0 or n == 1000]
                datasets_to_run.extend(selected)
            else:
                datasets_to_run.extend([f for _, f in gocj_files])
    elif args.all:
        if os.path.isdir(DATASETS_DIR):
            for file in sorted(os.listdir(DATASETS_DIR)):
                if file.endswith(".json"):
                    datasets_to_run.append(os.path.join(DATASETS_DIR, file))
    else:
        # Default: dataset standar (10, 30, 60)
        if os.path.isdir(DATASETS_DIR):
            for file in ["dataset_10.json", "dataset_30.json", "dataset_60.json"]:
                p = os.path.join(DATASETS_DIR, file)
                if os.path.isfile(p):
                    datasets_to_run.append(p)
        print("\n[INFO] Menjalankan dataset standar cepat (10, 30, 60).")
        print("[INFO] Untuk menguji dataset GoCJ (100 - 1000):")
        print("       python benchmark.py -d 100                     (uji 100 task)")
        print("       python benchmark.py -d 500                     (uji 500 task)")
        print("       python benchmark.py -d 1000                    (uji 1000 task)")
        print("       python benchmark.py --gocj                     (uji seluruh GoCJ 100-1000)")
        print("       python benchmark.py --gocj-step 200            (uji GoCJ bertahap)")

    if not datasets_to_run:
        print("[ERROR] Tidak ada dataset JSON yang ditemukan.")
        sys.exit(1)

    algos = ALGORITHMS if args.algorithm == "all" else [args.algorithm]

    csv_rows = []
    headers = [
        "Dataset", "Algoritma", "N_Task", "Prediksi_Makespan",
        "Makespan_Aktual", "Gap_Persen", "Throughput",
        "Utilization_Persen", "Imbalance"
    ]

    print("\n" + "-" * 118)
    print(f"{'Dataset':<22} | {'Algoritma':<9} | {'Tasks':<5} | {'Prediksi (s)':<12} | {'Aktual (s)':<12} | {'Gap (%)':<8} | {'Throughput':<10} | {'Util (%)':<9} | {'Imbalance':<10}")
    print("-" * 118)

    for ds_path in datasets_to_run:
        ds_name = os.path.basename(ds_path)
        with open(ds_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            tasks = raw_data.get("tasks", raw_data) if isinstance(raw_data, dict) else raw_data

        for algo in algos:
            # Beri jeda 1 detik antar run untuk pembersihan worker
            time.sleep(1)

            try:
                res = run_experiment(algo, tasks)
                metrics = res.get("metrics", {})
                n_task = len(tasks)
                pred_ms = metrics.get("predicted_makespan_seconds", 0.0)
                act_ms = metrics.get("actual_makespan_seconds", 0.0)
                gap = metrics.get("gap_percentage", 0.0)
                throughput = metrics.get("throughput_tasks_per_second", 0.0)
                util = metrics.get("average_utilization_percent", 0.0)
                imbalance = metrics.get("degree_of_imbalance", 0.0)

                print(f"{ds_name:<22} | {algo.upper():<9} | {n_task:<5} | {pred_ms:<12.4f} | {act_ms:<12.4f} | {gap:<8.2f} | {throughput:<10.4f} | {util:<9.2f} | {imbalance:<10.4f}")

                csv_rows.append({
                    "Dataset": ds_name,
                    "Algoritma": algo.upper(),
                    "N_Task": n_task,
                    "Prediksi_Makespan": f"{pred_ms:.4f}",
                    "Makespan_Aktual": f"{act_ms:.4f}",
                    "Gap_Persen": f"{gap:.2f}",
                    "Throughput": f"{throughput:.4f}",
                    "Utilization_Persen": f"{util:.2f}",
                    "Imbalance": f"{imbalance:.4f}",
                })
            except Exception as e:
                print(f"{ds_name:<15} | {algo.upper():<9} | {len(tasks):<5} | ERROR: {e}")

        print("-" * 112)

    # Simpan ke CSV
    if csv_rows:
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"\n[SUKSES] Hasil benchmark berhasil disimpan ke: {args.output}\n")


if __name__ == "__main__":
    main()
