import csv
import glob
import os

import numpy as np

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(root, "data")
WIN = 2.0  # saniye


def latest(label):
    files = sorted(glob.glob(os.path.join(data_dir, f"{label}_*.csv")))
    return files[-1]


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
    keep = t >= trim
    return t[keep] - t[keep][0], np.array(amps)[keep]


sets = {"bos": load("bos", 10), "bos2": load("bos2", 10), "yuruyor": load("yuruyor")}
valid = sets["bos"][1].mean(axis=0) > 3


def norm(a):
    a = a[:, valid]
    return a / a.mean(axis=1, keepdims=True)


ref = np.median(norm(sets["bos"][1]), axis=0)

windows = {}
for name, (t, a) in sets.items():
    dev = np.abs(norm(a) - ref).mean(axis=1)
    idx = (t // WIN).astype(int)
    vals = [dev[idx == i].mean() for i in np.unique(idx) if (idx == i).sum() >= 20]
    windows[name] = np.array(vals)
    w = windows[name]
    print(f"{name:8s}: {len(w):3d} pencere | min {w.min():.3f} | medyan {np.median(w):.3f} | max {w.max():.3f}")

thr = (np.median(windows["bos"]) + np.median(windows["yuruyor"])) / 2
print(f"\nEsik (iki medyanin ortasi): {thr:.3f}")
for name, w in windows.items():
    print(f"{name:8s}: pencerelerin %{100 * (w > thr).mean():.0f}'i esigin ustunde")