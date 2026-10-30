import os
import time
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

WORKER_ID = os.getenv("WORKER_ID", "WORKER-UNKNOWN")
HOST_ID = os.getenv("HOST_ID", "HOST-UNKNOWN")
CAPACITY = float(os.getenv("CAPACITY", "1.0"))
ITERATIONS_PER_UNIT = int(os.getenv("ITERATIONS_PER_UNIT", "80000"))


@app.get("/health")
def health():
    return jsonify({
        "status": "online",
        "worker_id": WORKER_ID,
        "host_id": HOST_ID,
        "capacity": CAPACITY
    })


@app.post("/execute")
def execute():
    data = request.get_json(force=True)

    task_id = data.get("task_id")
    workload = int(data.get("workload", 1))

    if not task_id or workload < 1 or workload > 100:
        return jsonify({"error": "Invalid task"}), 400

    iterations = int(workload * ITERATIONS_PER_UNIT / max(CAPACITY, 0.01))
    result = "maxmin-cloud"
    start = time.perf_counter()

    for i in range(iterations):
        result = hashlib.sha256(
            f"{result}-{i}".encode()
        ).hexdigest()

    duration = time.perf_counter() - start

    return jsonify({
        "task_id": task_id,
        "worker_id": WORKER_ID,
        "host_id": HOST_ID,
        "capacity": CAPACITY,
        "status": "completed",
        "workload": workload,
        "iterations": iterations,
        "execution_seconds": round(duration, 6),
        "result_hash": result
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)