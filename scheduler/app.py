import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

WORKER_IDS = [
    item.strip()
    for item in os.getenv(
        "WORKERS", "worker1,worker2,worker3,worker4"
    ).split(",")
    if item.strip()
]
WORKER_PORT = 8000
REQUEST_TIMEOUT = 3600
scheduler_lock = threading.Lock()


def worker_url(worker_id):
    return f"http://{worker_id}:{WORKER_PORT}"


def get_workers():
    result = []
    for worker_id in WORKER_IDS:
        try:
            response = requests.get(
                f"{worker_url(worker_id)}/health", timeout=3
            )
            response.raise_for_status()
            info = response.json()
            result.append({
                "id": worker_id,
                "host_id": info.get("host_id", "unknown"),
                "url": worker_url(worker_id),
                "online": True,
            })
        except requests.RequestException:
            result.append({
                "id": worker_id,
                "host_id": "unknown",
                "url": worker_url(worker_id),
                "online": False,
            })
    return result


def estimate_seconds(task, worker):
    """
    Estimasi waktu (detik) = workload / kapasitas worker.
    Kapasitas di sini disetel sama untuk semua worker sebagai baseline.
    Untuk eksperimen, sesuaikan capacity masing-masing worker.
    """
    workload = float(task["workload"])
    capacity = float(worker.get("capacity", 1.0))
    return workload / max(capacity, 0.001)


def max_min_schedule(tasks, workers):
    """
    Max-Min:
    1. Untuk setiap tugas yang belum dijadwalkan, cari worker dengan
       predicted finish time terkecil.
    2. Pilih tugas yang memiliki predicted finish time minimum terbesar.
    3. Tetapkan tugas tersebut dan perbarui ketersediaan worker.
    """
    available = {w["id"]: 0.0 for w in workers}
    capacities = {w["id"]: float(w.get("capacity", 1.0)) for w in workers}
    assignments = []
    pending = [dict(task) for task in tasks]

    while pending:
        best_task = None
        best_worker = None
        best_finish = -1.0
        best_duration = 0.0

        for task in pending:
            for worker in workers:
                wid = worker["id"]
                duration = float(task["workload"]) / max(capacities[wid], 0.001)
                finish = available[wid] + duration

                # Worker tercepat untuk tugas ini.
                # Di antara nilai minimum setiap tugas, pilih yang terbesar.
                if best_task is None:
                    per_task_min_finish = finish
                    per_task_min_worker = wid
                    per_task_min_duration = duration
                else:
                    per_task_min_finish = finish
                    per_task_min_worker = wid
                    per_task_min_duration = duration

                # Simpan minimum per task untuk dibandingkan di bawah.
                # Perhitungan ini dilakukan eksplisit agar logika Max-Min jelas.
            task_candidates = []
            for worker in workers:
                wid = worker["id"]
                duration = float(task["workload"]) / max(capacities[wid], 0.001)
                task_candidates.append((available[wid] + duration, wid, duration))
            finish, wid, duration = min(task_candidates, key=lambda item: item[0])

            if finish > best_finish:
                best_finish = finish
                best_task = task
                best_worker = wid
                best_duration = duration

        assignments.append({
            "task_id": best_task["id"],
            "worker_id": best_worker,
            "host_id": next(
                (w.get("host_id", "unknown") for w in workers
                 if w["id"] == best_worker),
                "unknown"
            ),
            "workload": float(best_task["workload"]),
            "estimated_duration_seconds": round(best_duration, 4),
            "estimated_finish_seconds": round(best_finish, 4),
        })
        available[best_worker] += best_duration
        pending.remove(best_task)

    return assignments


def min_min_schedule(tasks, workers):
    """Pembanding Min-Min: pilih tugas dengan minimum finish time terkecil."""
    available = {w["id"]: 0.0 for w in workers}
    capacities = {w["id"]: float(w.get("capacity", 1.0)) for w in workers}
    pending = [dict(task) for task in tasks]
    assignments = []

    while pending:
        candidates = []
        for task in pending:
            for worker in workers:
                wid = worker["id"]
                duration = float(task["workload"]) / max(capacities[wid], 0.001)
                finish = available[wid] + duration
                candidates.append((finish, task, wid, duration))

        finish, task, wid, duration = min(candidates, key=lambda item: item[0])
        assignments.append({
            "task_id": task["id"],
            "worker_id": wid,
            "host_id": next(
                (w.get("host_id", "unknown") for w in workers if w["id"] == wid),
                "unknown"
            ),
            "workload": float(task["workload"]),
            "estimated_duration_seconds": round(duration, 4),
            "estimated_finish_seconds": round(finish, 4),
        })
        available[wid] += duration
        pending.remove(task)

    return assignments


def fcfs_schedule(tasks, workers):
    """Pembanding FCFS: urutan tugas mengikuti input, worker paling cepat tersedia."""
    available = {w["id"]: 0.0 for w in workers}
    capacities = {w["id"]: float(w.get("capacity", 1.0)) for w in workers}
    assignments = []

    for task in tasks:
        candidates = []
        for worker in workers:
            wid = worker["id"]
            duration = float(task["workload"]) / max(capacities[wid], 0.001)
            candidates.append((available[wid] + duration, wid, duration, worker))
        finish, wid, duration, worker = min(candidates, key=lambda item: item[0])
        assignments.append({
            "task_id": task["id"],
            "worker_id": wid,
            "host_id": worker.get("host_id", "unknown"),
            "workload": float(task["workload"]),
            "estimated_duration_seconds": round(duration, 4),
            "estimated_finish_seconds": round(finish, 4),
        })
        available[wid] += duration

    return assignments


def execute_assignment(assignment, task_lookup):
    wid = assignment["worker_id"]
    payload = {
        "task_id": assignment["task_id"],
        "workload": task_lookup[assignment["task_id"]]["workload"],
    }
    started = time.perf_counter()
    response = requests.post(
        f"{worker_url(wid)}/execute",
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    result = response.json()
    result["scheduler_round_trip_seconds"] = round(elapsed, 6)
    return result


@app.get("/")
def index():
    return jsonify({
        "project": "Max-Min Scheduling Self-Hosted Demo",
        "endpoints": {
            "GET /health": "status scheduler",
            "GET /workers": "status semua worker",
            "POST /run": "jadwalkan dan eksekusi tugas",
        },
        "run_example": {
            "algorithm": "max-min",
            "tasks": [
                {"id": "T1", "workload": 4},
                {"id": "T2", "workload": 8},
                {"id": "T3", "workload": 3},
            ],
        },
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "scheduler"})


@app.get("/workers")
def workers_status():
    return jsonify({"workers": get_workers()})


@app.post("/run")
def run_tasks():
    if not scheduler_lock.acquire(blocking=False):
        return jsonify({"error": "Scheduler sedang menjalankan batch lain."}), 409

    try:
        body = request.get_json(silent=True) or {}
        algorithm = str(body.get("algorithm", "max-min")).lower()
        tasks = body.get("tasks", [])

        if not isinstance(tasks, list) or not tasks:
            return jsonify({
                "error": "Field 'tasks' harus berupa list yang tidak kosong."
            }), 400

        normalized_tasks = []
        seen_ids = set()
        for index, task in enumerate(tasks, start=1):
            if not isinstance(task, dict):
                return jsonify({"error": f"Tugas ke-{index} harus berupa object."}), 400
            task_id = str(task.get("id", f"T{index}"))
            try:
                workload = float(task["workload"])
            except (KeyError, TypeError, ValueError):
                return jsonify({
                    "error": f"Tugas {task_id} harus memiliki workload numerik."
                }), 400
            if workload <= 0:
                return jsonify({"error": f"Workload tugas {task_id} harus > 0."}), 400
            if task_id in seen_ids:
                return jsonify({"error": f"ID tugas duplikat: {task_id}"}), 400
            seen_ids.add(task_id)
            normalized_tasks.append({"id": task_id, "workload": workload})

        workers_info = get_workers()
        online_ids = {w["id"] for w in workers_info if w["online"]}
        workers = [
            {"id": w["id"], "host_id": w["host_id"], "capacity": 1.0}
            for w in workers_info if w["online"]
        ]
        if not workers:
            return jsonify({"error": "Tidak ada worker yang online."}), 503

        if algorithm == "max-min":
            assignments = max_min_schedule(normalized_tasks, workers)
        elif algorithm == "min-min":
            assignments = min_min_schedule(normalized_tasks, workers)
        elif algorithm == "fcfs":
            assignments = fcfs_schedule(normalized_tasks, workers)
        else:
            return jsonify({
                "error": "Algoritma tidak dikenal. Gunakan max-min, min-min, atau fcfs."
            }), 400

        # Jika worker offline setelah pengecekan awal, beri error sebelum eksekusi.
        unavailable = sorted({
            a["worker_id"] for a in assignments if a["worker_id"] not in online_ids
        })
        if unavailable:
            return jsonify({"error": "Worker offline", "workers": unavailable}), 503

        task_lookup = {task["id"]: task for task in normalized_tasks}
        start = time.perf_counter()
        results = []
        failures = []

        # Jalankan antrean setiap worker secara berurutan, sementara worker
        # yang berbeda dapat bekerja paralel. Urutan assignment mengikuti hasil
        # penjadwalan Max-Min/Min-Min/FCFS.
        assignments_by_worker = {w["id"]: [] for w in workers}
        for assignment in assignments:
            assignments_by_worker[assignment["worker_id"]].append(assignment)

        def run_worker_queue(worker_assignments):
            worker_results = []
            worker_failures = []
            for assignment in worker_assignments:
                try:
                    worker_results.append(
                        execute_assignment(assignment, task_lookup)
                    )
                except Exception as exc:
                    worker_failures.append({
                        "task_id": assignment["task_id"],
                        "worker_id": assignment["worker_id"],
                        "error": str(exc),
                    })
            return worker_results, worker_failures

        with ThreadPoolExecutor(max_workers=len(workers)) as executor:
            futures = [
                executor.submit(run_worker_queue, queue)
                for queue in assignments_by_worker.values()
                if queue
            ]
            for future in as_completed(futures):
                worker_results, worker_failures = future.result()
                results.extend(worker_results)
                failures.extend(worker_failures)

        makespan = time.perf_counter() - start
        results.sort(key=lambda item: item.get("task_id", ""))
        response_body = {
            "algorithm": algorithm,
            "task_count": len(normalized_tasks),
            "worker_count": len(workers),
            "assignments": assignments,
            "results": results,
            "failures": failures,
            "metrics": {
                "makespan_seconds": round(makespan, 6),
                "completed_tasks": len(results),
                "failed_tasks": len(failures),
                "throughput_tasks_per_second": round(
                    len(results) / makespan, 6
                ) if makespan > 0 else 0,
            },
            "note": (
                "Makespan dan throughput diukur dari eksekusi nyata pada container "
                "lokal; estimasi scheduler memakai workload dan kapasitas baseline."
            ),
        }
        status_code = 207 if failures else 200
        return jsonify(response_body), status_code
    finally:
        scheduler_lock.release()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
