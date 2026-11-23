import csv
import glob
import os

import numpy as np

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(root, "data")


def latest(label):
    files = sorted(glob.glob(os.path.join(data_dir, f"{label}_*.csv")))
    return files[-1] if files else None


def load(path):
    amps, rssi = [], []
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f):
            try:
                vals = [int(x) for x in row[-1].strip("[]").split(",")]
                if len(vals) != 384:
                    continue
                a = np.array(vals, dtype=float)
                amps.append(np.hypot(a[0::2], a[1::2]))
                rssi.append(int(row[4]))
            except (ValueError, IndexError):
                continue
    return np.array(amps), np.array(rssi)


results = {}
for label in ("bos", "yuruyor"):
    path = latest(label)
    if path is None:
        print(f"{label}: kayit bulunamadi")
        continue
    amps, rssi = load(path)
    results[label] = (os.path.basename(path), amps, rssi)

if "bos" not in results or "yuruyor" not in results:
    raise SystemExit("Iki kayit da gerekli.")

# Bos odada anlamli (sifir olmayan) alt tasiyicilari sec
valid = results["bos"][1].mean(axis=0) > 3
print(f"Kullanilan alt tasiyici sayisi: {valid.sum()} / 192\n")

summary = {}
for label, (name, amps, rssi) in results.items():
    a = amps[:, valid]
    a = a / a.mean(axis=1, keepdims=True)
    mean_amp = a.mean()
    temporal_std = a.std(axis=0).mean()
    summary[label] = temporal_std / mean_amp
    print(f"[{label}] dosya: {name}")
    print(f"  paket sayisi        : {len(a)}")
    print(f"  RSSI ort / std      : {rssi.mean():.1f} / {rssi.std():.2f}")
    print(f"  ortalama genlik     : {mean_amp:.2f}")
    print(f"  zamansal oynama (CV): {summary[label]:.3f}\n")

print(f"Yuruyor / bos oynama orani: {summary['yuruyor'] / summary['bos']:.2f}x")