import hashlib
import os
import time
from flask import Flask, jsonify, request

app = Flask(__name__)
WORKER_ID = os.getenv("WORKER_ID", "worker-unknown")
HOST_ID = os.getenv("HOST_ID", "host-unknown")
CAPACITY = float(os.getenv("CAPACITY", "1.0"))
ITERATIONS_PER_UNIT = int(os.getenv("ITERATIONS_PER_UNIT", "150000"))


def perform_work(workload):
    """
    Komputasi CPU-bound deterministik yang benar-benar berjalan.
    Workload dibatasi agar endpoint tidak menerima pekerjaan tanpa batas.
    """
    units = int(workload)
    if units < 1 or units > 100:
        raise ValueError("workload harus berupa bilangan bulat antara 1 dan 100")

    start = time.perf_counter()
    digest = b"maxmin-demo"
    iterations = int(units * ITERATIONS_PER_UNIT / max(CAPACITY, 0.01))
    for i in range(iterations):
        digest = hashlib.sha256(digest + str(i).encode("utf-8")).digest()
    elapsed = time.perf_counter() - start

    return {
        "iterations": iterations,
        "checksum": digest.hex(),
        "execution_seconds": round(elapsed, 6),
    }


@app.get("/")
def index():
    return jsonify({
        "worker_id": WORKER_ID,
        "host_id": HOST_ID,
        "capacity": CAPACITY,
        "message": "Worker aktif",
    })


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "worker_id": WORKER_ID,
        "host_id": HOST_ID,
        "capacity": CAPACITY,
    })


@app.post("/execute")
def execute():
    body = request.get_json(silent=True) or {}
    task_id = str(body.get("task_id", "unnamed-task"))

    try:
        workload = float(body["workload"])
        if not workload.is_integer():
            return jsonify({"error": "workload harus berupa bilangan bulat."}), 400
        workload = int(workload)
        result = perform_work(workload)
    except KeyError:
        return jsonify({"error": "Field workload wajib diisi."}), 400
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "task_id": task_id,
        "worker_id": WORKER_ID,
        "host_id": HOST_ID,
        "capacity": CAPACITY,
        "workload": workload,
        **result,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)
