import csv
import glob
import os

import matplotlib.pyplot as plt
import numpy as np

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(root, "data")


def latest(label):
    files = sorted(glob.glob(os.path.join(data_dir, f"{label}_*.csv")))
    return files[-1] if files else None


def load(path):
    t, amps = [], []
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f):
            try:
                vals = [int(x) for x in row[-1].strip("[]").split(",")]
                if len(vals) != 384:
                    continue
                a = np.array(vals, dtype=float)
                amps.append(np.hypot(a[0::2], a[1::2]))
                t.append(float(row[0]))
            except (ValueError, IndexError):
                continue
    t = np.array(t)
    return t - t[0], np.array(amps)


files = {label: latest(label) for label in ("bos", "yuruyor")}
if None in files.values():
    raise SystemExit("bos ve yuruyor kayitlari gerekli.")

data = {label: load(path) for label, path in files.items()}
keep = data["bos"][0] >= 10
data["bos"] = (data["bos"][0][keep] - data["bos"][0][keep][0], data["bos"][1][keep])
valid = data["bos"][1].mean(axis=0) > 3

norm = {}
for label, (t, a) in data.items():
    a = a[:, valid]
    a = a / a.mean(axis=1, keepdims=True)
    norm[label] = (t, a)

# Bos odanin tipik genlik profili (referans)
ref = np.median(norm["bos"][1], axis=0)

N = 20  # hareketli ortalama penceresi (paket)
fig, ax = plt.subplots(figsize=(10, 4))
for label, (t, a) in norm.items():
    dev = np.abs(a - ref).mean(axis=1)
    smooth = np.convolve(dev, np.ones(N) / N, mode="valid")
    ax.plot(t[N - 1:], smooth, label=label)
    print(f"[{label}] referanstan ortalama sapma: {dev.mean():.4f}")

ax.set_xlabel("Zaman (sn)")
ax.set_ylabel("Referanstan sapma (genlik, normalize)")
ax.set_title("Bos oda referansina gore sapma")
ax.legend()
ax.grid(True, alpha=0.3)

out = os.path.join(data_dir, "karsilastirma.png")
fig.savefig(out, dpi=120, bbox_inches="tight")
print(f"Grafik kaydedildi: {out}")
plt.show()