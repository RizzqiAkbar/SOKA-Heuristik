#!/usr/bin/env python3
"""
Script Konversi Dataset GoCJ (.txt) ke JSON untuk SOKA Real-Life.
Membaca file GoCJ_Dataset_<N>.txt dan menghasilkan GoCJ_Dataset_<N>.json.
Workload dinormalisasi ke skala 1 - 100 agar sesuai dengan kapasitas komputasi worker Docker.
"""

import glob
import json
import os
import re

DATASETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")


def convert_gocj_file(txt_path):
    filename = os.path.basename(txt_path)
    match = re.search(r"GoCJ_Dataset_(\d+)\.txt", filename)
    if not match:
        return None

    task_count = int(match.group(1))
    json_filename = f"GoCJ_Dataset_{task_count}.json"
    json_path = os.path.join(DATASETS_DIR, json_filename)

    tasks = []
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    for i, line in enumerate(lines, start=1):
        try:
            length_mi = int(line)
        except ValueError:
            continue

        # Normalisasi: length MI (15.000 - 900.000) dibagi 10.000 menjadi workload (1 - 90).
        # Dipastikan selalu berada dalam batas 1..100 integer.
        workload = max(1, min(100, int(round(length_mi / 10000.0))))

        tasks.append({
            "id": f"T{i:04d}",
            "workload": workload,
            "length_mi": length_mi
        })

    with open(json_path, "w", encoding="utf-8") as out:
        json.dump(tasks, out, indent=2)

    return json_path, len(tasks)


def main():
    pattern = os.path.join(DATASETS_DIR, "GoCJ_Dataset_*.txt")
    txt_files = sorted(
        glob.glob(pattern),
        key=lambda p: int(re.search(r"\d+", os.path.basename(p)).group())
    )

    if not txt_files:
        print("[ERROR] Tidak ditemukan file GoCJ_Dataset_*.txt di", DATASETS_DIR)
        return

    print(f"[INFO] Menemukan {len(txt_files)} file GoCJ Dataset...")
    converted = []
    for f in txt_files:
        res = convert_gocj_file(f)
        if res:
            json_path, count = res
            converted.append((os.path.basename(json_path), count))
            print(f"  [OK] {os.path.basename(f)} -> {os.path.basename(json_path)} ({count} tasks)")

    print(f"\n[SUKSES] Berhasil mengonversi {len(converted)} file GoCJ ke JSON di {DATASETS_DIR}\n")


if __name__ == "__main__":
    main()
