"""
Baca hasil_metrik_perbandingan.csv (ditulis otomatis oleh Main.java setelah
menjalankan Max-Min, Min-Min, FCFS di semua skenario) dan bikin 5 PNG --
satu per metrik, satu garis berwarna per algoritma, X = jumlah task.

Cara pakai:
    1. Jalankan Main.java (sudah di-update supaya loop 3 algoritma x
       semua skenario 100..1000 kelipatan 50, dan nulis
       hasil_metrik_perbandingan.csv di root project).
    2. Copy hasil_metrik_perbandingan.csv ke folder yang sama dengan
       script ini (atau edit CSV_PATH di bawah).
    3. pip install pandas matplotlib   (kalau belum ada)
    4. python buat_grafik.py
    5. Lihat folder grafik/ -> 5 file PNG siap tempel ke laporan/slide.
"""
import os
import pandas as pd
import matplotlib.pyplot as plt

CSV_PATH = "hasil_metrik_perbandingan.csv"
OUT_DIR = "grafik"

# Palet warna beda-beda biar jelas per algoritma
WARNA = {
    "Max-Min": "#21295C",   # navy
    "Min-Min": "#1C7293",   # teal
    "FCFS": "#E07A5F",      # oranye
}

# (nama kolom di CSV, judul chart, label sumbu Y, nama file output)
METRIK = [
    ("Makespan_Aktual",      "Makespan vs Jumlah Task",              "Makespan (detik)",          "1_makespan.png"),
    ("Throughput",           "Throughput vs Jumlah Task",            "Throughput (task/detik)",   "2_throughput.png"),
    ("Utilization_Persen",   "Resource Utilization vs Jumlah Task",  "Utilisasi (%)",              "3_utilization.png"),
    ("Imbalance",            "Degree of Imbalance vs Jumlah Task",   "Stdev waktu selesai VM (detik)", "4_imbalance.png"),
    ("Total_Cost",           "Total Cost vs Jumlah Task",            "Total Cost (unit biaya)",    "5_total_cost.png"),
]


def main():
    df = pd.read_csv(CSV_PATH)
    df = df.sort_values("N_Task")
    os.makedirs(OUT_DIR, exist_ok=True)

    for kolom, judul, label_y, filename in METRIK:
        plt.figure(figsize=(8, 5))
        for algo, grup in df.groupby("Algoritma", sort=False):
            grup = grup.sort_values("N_Task")
            plt.plot(
                grup["N_Task"], grup[kolom],
                marker="o", linewidth=2,
                label=algo, color=WARNA.get(algo),
            )
        plt.title(judul)
        plt.xlabel("Jumlah Task")
        plt.ylabel(label_y)
        plt.legend(title="Algoritma")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        out_path = os.path.join(OUT_DIR, filename)
        plt.savefig(out_path, dpi=200)
        plt.close()
        print("Tersimpan:", out_path)


if __name__ == "__main__":
    main()
