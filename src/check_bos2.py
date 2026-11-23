import csv
import glob
import os

import numpy as np

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(root, "data")


def latest(label):
    files = sorted(glob.glob(os.path.join(data_dir, f"{label}_*.csv")))
    return files[-1] if files else None


def load(label, trim=0.0):
    t, amps = [], []
    with open(latest(label), encoding="utf-8") as f:
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
    t = t - t[0]
    return np.array(amps)[t >= trim]


bos = load("bos", trim=10)
bos2 = load("bos2", trim=10)
yur = load("yuruyor")

valid = bos.mean(axis=0) > 3


def norm(a):
    a = a[:, valid]
    return a / a.mean(axis=1, keepdims=True)


ref = np.median(norm(bos), axis=0)

print("Referans: bos kaydi (ilk 10 sn atildi)\n")
for name, a in (("bos  (referansin kendisi)", bos),
                ("bos2 (yeni, gorulmemis)  ", bos2),
                ("yuruyor                  ", yur)):
    dev = np.abs(norm(a) - ref).mean(axis=1)
    print(f"{name}: ort {dev.mean():.4f} | %95 {np.percentile(dev, 95):.4f} | paket {len(dev)}")