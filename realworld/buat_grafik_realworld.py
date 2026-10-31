"""
Grafik hasil real world (Max-Min di cluster k3s).

Membaca hasil_ringkas.txt (100/200/300/500 task) dan hasil_ringkas_2.txt (400-1000 task) bila ada,
lalu membuat 4 PNG di folder grafik/:
  1_prediksi_vs_aktual.png         makespan prediksi vs aktual per jumlah task
  2_utilisasi_node.png             utilisasi tiap node per jumlah task
  3_selisih_vs_jumlah_task.png     selisih prediksi-aktual per jumlah task
  4_selisih_vs_panjang_task.png    selisih vs rata-rata panjang task (100 task)

Cara pakai (dari folder realworld/):
    python3 buat_grafik_realworld.py
"""
import os
import re
import matplotlib.pyplot as plt

HASIL = ["hasil_ringkas.txt", "hasil_ringkas_2.txt"]
OUT_DIR = "grafik"
TOTAL_VCPU = 6

# Run 100 task di luar batch (diambil dari keluaran run_plan.py): (rata-rata task detik, selisih %)
PEMANASAN = [(6 * 60 / 100, 170.0), (6 * 60 / 100, 155.0), (6 * 60 / 100, 110.0)]
TARGET_600 = (6 * 600 / 100, 25.7)

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
PREDIKSI = "#2a78d6"   # biru (kategori 1)
AKTUAL = "#eb6834"     # oranye (kategori 2)
PC1 = PREDIKSI         # utilisasi: warna = PC, gaya garis = jumlah vCPU
PC2 = AKTUAL

NODES = [
    ("vm-a1", "vm-a1 (PC 1, 2 vCPU)", PC1, "-", "o"),
    ("vm-a2", "vm-a2 (PC 1, 1 vCPU)", PC1, (0, (4, 3)), "s"),
    ("vm-b1", "vm-b1 (PC 2, 2 vCPU)", PC2, "-", "o"),
    ("vm-b2", "vm-b2 (PC 2, 1 vCPU)", PC2, (0, (4, 3)), "s"),
]


def koma(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def baca_hasil():
    runs = {}
    for nama in HASIL:
        if not os.path.exists(nama):
            continue
        teks = open(nama, encoding="utf-8").read()
        for blok in re.split(r"##### ", teks)[1:]:
            n = int(re.match(r"(\d+) task", blok).group(1))
            pred = re.search(r"Prediksi makespan\s*:\s*([\d.]+)", blok)
            akt = re.search(r"Makespan aktual\s*:\s*([\d.]+)", blok)
            if not (pred and akt):      # run yang kena batas waktu tidak punya hasil
                continue
            util = {}
            for m in re.finditer(r"^(vm-\w+)\s+\d+\s+\d+\s+([\d.]+)\s*$", blok, re.M):
                util[m.group(1)] = float(m.group(2))
            runs[n] = {"n": n, "pred": float(pred.group(1)), "akt": float(akt.group(1)), "util": util}
    return [runs[n] for n in sorted(runs)]


def gaya(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=10, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)


def simpan(fig, nama):
    os.makedirs(OUT_DIR, exist_ok=True)
    fig.savefig(os.path.join(OUT_DIR, nama), dpi=200, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def grafik_makespan(runs):
    fig, ax = plt.subplots(figsize=(11, 4.8), facecolor=SURFACE)
    gaya(ax)
    lebar = 0.38
    tinggi = max(r["akt"] for r in runs)
    for i, r in enumerate(runs):
        ax.bar(i - lebar / 2, r["pred"], lebar, color=PREDIKSI, edgecolor=SURFACE, linewidth=1.5,
               label="Prediksi (simulasi)" if i == 0 else None)
        ax.bar(i + lebar / 2, r["akt"], lebar, color=AKTUAL, edgecolor=SURFACE, linewidth=1.5,
               label="Aktual (cluster k3s)" if i == 0 else None)
        selisih = (r["akt"] - r["pred"]) / r["pred"] * 100
        ax.text(i + lebar / 2, r["akt"] + tinggi * 0.015, f"{koma(r['akt'], 0)}\n+{koma(selisih, 0)}%",
                ha="center", va="bottom", fontsize=8, color=INK)
        ax.text(i - lebar / 2, r["pred"] + tinggi * 0.015, f"{koma(r['pred'], 0)}", ha="center",
                va="bottom", fontsize=8, color=INK2)
    ax.set_xticks(range(len(runs)))
    ax.set_xticklabels([str(r["n"]) for r in runs], color=INK, fontsize=10)
    ax.set_xlabel("Jumlah task (target prediksi = 3 detik × jumlah task)", color=INK2, fontsize=10)
    ax.set_ylabel("Makespan (detik)", color=INK2, fontsize=10)
    ax.set_ylim(0, tinggi * 1.15)
    ax.set_title("Makespan Max-Min: prediksi simulasi vs aktual di cluster", loc="left",
                 color=INK, fontsize=12, pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=10,
              labelcolor=INK2, handlelength=1, borderaxespad=0)
    simpan(fig, "1_prediksi_vs_aktual.png")


def grafik_utilisasi(runs):
    fig, ax = plt.subplots(figsize=(10, 4.8), facecolor=SURFACE)
    gaya(ax)
    xs = [r["n"] for r in runs]
    for node, label, warna, garis, marker in NODES:
        ys = [r["util"][node] for r in runs]
        ax.plot(xs, ys, color=warna, linestyle=garis, linewidth=2, marker=marker, markersize=7,
                markeredgecolor=SURFACE, markeredgewidth=1.5, label=label)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(x) for x in xs], color=INK, fontsize=10)
    ax.set_xlabel("Jumlah task", color=INK2, fontsize=10)
    ax.set_ylabel("Utilisasi node (%)", color=INK2, fontsize=10)
    ax.set_ylim(0, 110)
    ax.set_yticks(range(0, 101, 20))
    ax.set_title("Utilisasi node per jumlah task (biru = PC 1, oranye = PC 2)", loc="left",
                 color=INK, fontsize=12, pad=52)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=10,
              labelcolor=INK2, handlelength=2.4, borderaxespad=0)
    simpan(fig, "2_utilisasi_node.png")


def grafik_selisih_jumlah(runs):
    fig, ax = plt.subplots(figsize=(10, 4.4), facecolor=SURFACE)
    gaya(ax)
    xs = [r["n"] for r in runs]
    ys = [(r["akt"] - r["pred"]) / r["pred"] * 100 for r in runs]
    ax.plot(xs, ys, color=AKTUAL, linewidth=2, marker="o", markersize=8,
            markeredgecolor=SURFACE, markeredgewidth=2)
    for x, y in zip(xs, ys):
        ax.annotate(f"{koma(y)}%", (x, y), xytext=(0, 9), textcoords="offset points",
                    ha="center", fontsize=9, color=INK)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(x) for x in xs], color=INK, fontsize=10)
    ax.set_xlabel("Jumlah task", color=INK2, fontsize=10)
    ax.set_ylabel("Selisih aktual terhadap prediksi (%)", color=INK2, fontsize=10)
    ax.set_ylim(0, max(ys) * 1.2)
    ax.set_title("Selisih prediksi-aktual per jumlah task (task rata-rata sekitar 18 detik)",
                 loc="left", color=INK, fontsize=12, pad=14)
    simpan(fig, "3_selisih_vs_jumlah_task.png")


def grafik_selisih_panjang(runs):
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=SURFACE)
    gaya(ax)
    r100 = next((r for r in runs if r["n"] == 100), None)
    titik = list(PEMANASAN) + [TARGET_600]
    if r100:
        titik.append((TOTAL_VCPU * r100["pred"] / r100["n"], (r100["akt"] - r100["pred"]) / r100["pred"] * 100))
    for x, y in titik:
        ax.scatter(x, y, s=90, color=AKTUAL, edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.annotate("pemanasan, 3 run: 110-170%", (PEMANASAN[1][0], PEMANASAN[1][1]), xytext=(10, -3),
                textcoords="offset points", fontsize=9, color=INK)
    if r100:
        x, y = titik[-1]
        ax.annotate(f"target 300: {koma(y)}%", (x, y), xytext=(10, 4), textcoords="offset points",
                    fontsize=9, color=INK)
    ax.annotate(f"target 600: {koma(TARGET_600[1])}%", TARGET_600, xytext=(0, -22),
                textcoords="offset points", fontsize=9, color=INK, ha="center")
    ax.set_xlim(0, 44)
    ax.set_ylim(0, 190)
    ax.set_xlabel("Rata-rata panjang task (detik) = 6 vCPU × prediksi ÷ jumlah task", color=INK2, fontsize=10)
    ax.set_ylabel("Selisih aktual terhadap prediksi (%)", color=INK2, fontsize=10)
    ax.set_title("100 task: selisih mengecil saat task lebih panjang", loc="left",
                 color=INK, fontsize=12, pad=14)
    simpan(fig, "4_selisih_vs_panjang_task.png")


if __name__ == "__main__":
    runs = baca_hasil()
    print("Ukuran terbaca:", [r["n"] for r in runs])
    grafik_makespan(runs)
    grafik_utilisasi(runs)
    grafik_selisih_jumlah(runs)
    grafik_selisih_panjang(runs)
    print("Selesai ->", OUT_DIR)
