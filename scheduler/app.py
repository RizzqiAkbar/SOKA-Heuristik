import os
import re
import json
import time
import math
import sqlite3
import threading
import requests
import psutil

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request, render_template

app = Flask(__name__)

DATABASE = os.getenv("DATABASE_PATH", "/app/data/experiments.db")
INVENTORY = os.getenv("INVENTORY_PATH", "/app/infrastructure/inventory.json")
DATASET = os.getenv("DATASET_PATH", "/app/dataset/tasks.json")

workers_raw = os.getenv("WORKERS", "[]")
try:
    WORKERS = json.loads(workers_raw)
except Exception:
    WORKERS = []
    for w in workers_raw.split(","):
        w = w.strip()
        if w:
            WORKERS.append({
                "id": w,
                "url": f"http://{w}:8000",
                "capacity": 1.0,
                "host": "HOST-01",
                "vm": f"VM-{w}"
            })

run_lock = threading.Lock()


def database():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    try:
        with database() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    algorithm TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    makespan REAL,
                    throughput REAL,
                    task_count INTEGER,
                    results TEXT
                )
            """)
    except Exception as e:
        print(f"Warning: Database initialization error: {e}")


def load_inventory():
    paths = [INVENTORY, "infrastructure/inventory.json", "../infrastructure/inventory.json"]
    for p in paths:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as file:
                return json.load(file)
    return {"datacenters": []}


def load_dataset(filename=None):
    if filename:
        candidate_paths = [
            os.path.join(os.path.dirname(DATASET), filename),
            os.path.join("datasets", filename),
            os.path.join("../datasets", filename),
            filename,
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                with open(p, encoding="utf-8") as file:
                    data = json.load(file)
                    tasks = data.get("tasks", data) if isinstance(data, dict) else data
                    name = data.get("dataset_name", filename) if isinstance(data, dict) else filename
                    return {"dataset_name": name, "tasks": tasks, "filename": filename}

    paths = [DATASET, "datasets/tasks.json", "../datasets/tasks.json"]
    for p in paths:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as file:
                data = json.load(file)
                tasks = data.get("tasks", data) if isinstance(data, dict) else data
                name = data.get("dataset_name", os.path.basename(p)) if isinstance(data, dict) else os.path.basename(p)
                return {"dataset_name": name, "tasks": tasks, "filename": os.path.basename(p)}
    return {"dataset_name": "Default Tasks", "tasks": [], "filename": "none"}


def worker_status():
    output = []
    for worker in WORKERS:
        try:
            response = requests.get(worker["url"] + "/health", timeout=2)
            online = response.ok
        except requests.RequestException:
            online = False

        output.append({
            **worker,
            "status": "online" if online else "offline"
        })
    return output


def schedule_tasks(tasks, algorithm):
    algo_key = algorithm.lower().replace("-", "")
    available = {w["id"]: 0.0 for w in WORKERS}
    assignments = []
    remaining = list(tasks)

    while remaining:
        candidates = []
        for task in remaining:
            estimates = []
            for worker in WORKERS:
                capacity = max(float(worker.get("capacity", 1)), 0.01)
                completion = (
                    available[worker["id"]]
                    + float(task["workload"]) / capacity
                )
                estimates.append((completion, worker))

            best_time, best_worker = min(estimates, key=lambda x: x[0])
            candidates.append((task, best_worker, best_time))

        if algo_key == "maxmin":
            selected = max(candidates, key=lambda x: x[2])
        elif algo_key == "minmin":
            selected = min(candidates, key=lambda x: x[2])
        else:  # FCFS
            task = remaining[0]
            worker = min(WORKERS, key=lambda w: available[w["id"]])
            selected = (
                task,
                worker,
                available[worker["id"]] + float(task["workload"]) / max(float(worker.get("capacity", 1)), 0.01)
            )

        task, worker, estimated = selected
        assignments.append({
            "task": task,
            "task_id": task["id"],
            "worker": worker,
            "worker_id": worker["id"],
            "estimated_completion": round(estimated, 4)
        })
        available[worker["id"]] = estimated
        remaining.remove(task)

    return assignments


def execute_worker_queue(worker, assigned_tasks):
    results = []
    for assignment in assigned_tasks:
        task = assignment["task"]
        start = time.perf_counter()

        try:
            response = requests.post(
                worker["url"] + "/execute",
                json={
                    "task_id": task["id"],
                    "workload": int(task["workload"])
                },
                timeout=300
            )
            response.raise_for_status()
            result = response.json()
            result["status"] = "completed"
        except Exception as error:
            result = {
                "task_id": task["id"],
                "worker_id": worker["id"],
                "status": "failed",
                "execution_seconds": round(time.perf_counter() - start, 6),
                "error": str(error)
            }

        result["scheduler_elapsed_seconds"] = round(time.perf_counter() - start, 6)
        results.append(result)

    return results


def run_experiment(algorithm, tasks):
    if not WORKERS:
        raise ValueError("No workers configured")

    statuses = worker_status()
    offline = [w["id"] for w in statuses if w["status"] != "online"]
    if offline:
        raise RuntimeError("Offline workers: " + ", ".join(offline))

    assignments = schedule_tasks(tasks, algorithm)

    queues = {w["id"]: [] for w in WORKERS}
    for assignment in assignments:
        queues[assignment["worker"]["id"]].append(assignment)

    started_at = datetime.now().isoformat(timespec="seconds")
    wall_start = time.perf_counter()
    all_results = []

    with ThreadPoolExecutor(max_workers=len(WORKERS)) as executor:
        futures = []
        for worker in WORKERS:
            if queues[worker["id"]]:
                futures.append(
                    executor.submit(
                        execute_worker_queue,
                        worker,
                        queues[worker["id"]]
                    )
                )
        for future in futures:
            all_results.extend(future.result())

    makespan = time.perf_counter() - wall_start
    finished_at = datetime.now().isoformat(timespec="seconds")

    completed = sum(1 for r in all_results if r.get("status") == "completed")
    throughput = completed / makespan if makespan > 0 else 0.0

    assignment_lookup = {str(a["task"]["id"]): a for a in assignments}
    for result in all_results:
        tid = str(result.get("task_id", ""))
        assignment = assignment_lookup.get(tid)
        if assignment:
            worker = assignment["worker"]
            result["host_id"] = worker.get("host", "unknown")
            result["vm_id"] = worker.get("vm", "unknown")
            result["estimated_completion"] = assignment["estimated_completion"]

    predicted_makespan = max((a["estimated_completion"] for a in assignments), default=0.0)
    gap_percentage = (
        abs(makespan - predicted_makespan) / predicted_makespan * 100
        if predicted_makespan > 0 else 0.0
    )

    worker_busy_times = {w["id"]: 0.0 for w in WORKERS}
    worker_task_counts = {w["id"]: 0 for w in WORKERS}
    for res in all_results:
        wid = res.get("worker_id")
        if wid in worker_busy_times:
            worker_busy_times[wid] += res.get("execution_seconds", 0.0)
            worker_task_counts[wid] += 1

    total_busy = sum(worker_busy_times.values())
    worker_count = len(WORKERS)
    utilization_percent = (
        (total_busy / (worker_count * makespan)) * 100
        if (worker_count > 0 and makespan > 0) else 0.0
    )
    mean_busy = total_busy / worker_count if worker_count > 0 else 0.0
    variance = (
        sum((b - mean_busy) ** 2 for b in worker_busy_times.values()) / worker_count
        if worker_count > 0 else 0.0
    )
    degree_of_imbalance = math.sqrt(variance)

    metrics = {
        "predicted_makespan_seconds": round(predicted_makespan, 4),
        "actual_makespan_seconds": round(makespan, 6),
        "gap_percentage": round(gap_percentage, 2),
        "throughput_tasks_per_second": round(throughput, 4),
        "average_utilization_percent": round(utilization_percent, 2),
        "degree_of_imbalance": round(degree_of_imbalance, 4),
        "completed_tasks": completed,
        "failed_tasks": len(tasks) - completed,
        "worker_stats": {
            wid: {
                "tasks_assigned": sum(1 for a in assignments if a["worker"]["id"] == wid),
                "tasks_completed": worker_task_counts[wid],
                "busy_seconds": round(worker_busy_times[wid], 4),
                "utilization_percent": round(
                    (worker_busy_times[wid] / makespan) * 100, 2
                ) if makespan > 0 else 0.0,
            }
            for wid in sorted(worker_busy_times.keys())
        }
    }

    experiment = {
        "algorithm": algorithm.upper(),
        "started_at": started_at,
        "finished_at": finished_at,
        "makespan": round(makespan, 6),
        "throughput": round(throughput, 4),
        "task_count": len(tasks),
        "completed": completed,
        "failed": len(tasks) - completed,
        "metrics": metrics,
        "assignments": [
            {
                "task_id": a["task"]["id"],
                "workload": a["task"]["workload"],
                "worker": a["worker"]["id"],
                "worker_id": a["worker"]["id"],
                "host": a["worker"].get("host", "unknown"),
                "vm": a["worker"].get("vm", "unknown"),
                "estimated_completion": a["estimated_completion"]
            }
            for a in assignments
        ],
        "results": all_results
    }

    try:
        with database() as conn:
            conn.execute("""
                INSERT INTO experiments
                (algorithm, started_at, finished_at, makespan,
                 throughput, task_count, results)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                experiment["algorithm"],
                started_at,
                finished_at,
                experiment["makespan"],
                experiment["throughput"],
                len(tasks),
                json.dumps(experiment)
            ))
    except Exception as e:
        print(f"Warning: Failed to save experiment to DB: {e}")

    return experiment


@app.get("/")
def dashboard():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "scheduler"})


@app.get("/workers")
def api_workers():
    statuses = worker_status()
    workers_list = [
        {
            "id": w["id"],
            "host_id": w.get("host", "unknown"),
            "capacity": float(w.get("capacity", 1.0)),
            "online": w["status"] == "online",
            "url": w.get("url", "")
        }
        for w in statuses
    ]
    return jsonify({"workers": workers_list})


@app.get("/api/status")
def api_status():
    inventory = load_inventory()
    datacenters = inventory.get("datacenters", [])

    hosts = [
        host
        for dc in datacenters
        for host in dc.get("hosts", [])
    ]

    vms = [
        vm
        for host in hosts
        for vm in host.get("vms", [])
    ]

    workers = worker_status()

    return jsonify({
        "datacenter_count": len(datacenters),
        "host_count": len(hosts),
        "vm_count": len(vms),
        "workers": workers,
        "inventory": inventory,
        "scheduler_resources": {
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "ram_percent": psutil.virtual_memory().percent,
            "ram_total_gb": round(
                psutil.virtual_memory().total / 1024**3, 2
            )
        }
    })


@app.get("/api/datasets")
def api_datasets_list():
    dirs = [os.path.dirname(DATASET), "datasets", "../datasets"]
    found = []
    for d in dirs:
        if os.path.isdir(d):
            files = [f for f in os.listdir(d) if f.endswith(".json")]
            if files:
                def sort_key(name):
                    m = re.search(r"(\d+)", name)
                    num = int(m.group(1)) if m else 99999
                    return (0 if "dataset_" in name else (1 if "GoCJ" in name else 2), num, name)
                found = sorted(files, key=sort_key)
                break
    return jsonify(found)


@app.get("/api/dataset")
def api_dataset():
    file_param = request.args.get("file")
    return jsonify(load_dataset(file_param))


@app.post("/api/run")
def api_run():
    if not run_lock.acquire(blocking=False):
        return jsonify({"error": "An experiment is already running"}), 409

    try:
        data = request.get_json(silent=True) or {}
        algorithm = data.get("algorithm", "maxmin")
        dataset_file = data.get("dataset_file")

        # Use tasks provided or fallback to dataset
        tasks = data.get("tasks")
        if not tasks:
            dataset = load_dataset(dataset_file)
            tasks = dataset.get("tasks", [])

        if not tasks:
            return jsonify({"error": "Dataset is empty"}), 400

        result = run_experiment(algorithm, tasks)
        return jsonify(result)

    except Exception as error:
        return jsonify({"error": str(error)}), 500

    finally:
        run_lock.release()


@app.post("/run")
def run_tasks():
    if not run_lock.acquire(blocking=False):
        return jsonify({"error": "Scheduler is busy running another batch"}), 409

    try:
        body = request.get_json(silent=True) or {}
        algorithm = body.get("algorithm", "max-min")
        tasks = body.get("tasks", [])

        if isinstance(tasks, dict) and "tasks" in tasks:
            tasks = tasks["tasks"]

        if not isinstance(tasks, list) or not tasks:
            return jsonify({"error": "Field 'tasks' must be a non-empty list."}), 400

        result = run_experiment(algorithm, tasks)
        return jsonify(result)

    except Exception as error:
        return jsonify({"error": str(error)}), 500

    finally:
        run_lock.release()


@app.get("/api/history")
def api_history():
    try:
        with database() as conn:
            rows = conn.execute("""
                SELECT id, algorithm, started_at, makespan,
                       throughput, task_count
                FROM experiments
                ORDER BY id DESC
                LIMIT 30
            """).fetchall()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify([])


@app.get("/api/export")
def api_export():
    try:
        with database() as conn:
            rows = conn.execute("""
                SELECT id, algorithm, started_at, finished_at,
                       makespan, throughput, task_count, results
                FROM experiments
                ORDER BY id DESC
            """).fetchall()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify([])


initialize_database()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)