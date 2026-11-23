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


def load(label, trim=10.0):
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


# Kullanilan alt tasiyicilar ve referans: bos kayittan
_, bos_amps = load("bos")
valid = bos_amps.mean(axis=0) > 3


def norm(a):
    a = a[:, valid]
    return a / a.mean(axis=1, keepdims=True)


ref = np.median(norm(bos_amps), axis=0)


def windows(label):
    t, a = load(label)
    n = norm(a)
    idx = (t // WIN).astype(int)
    feats = []
    for i in np.unique(idx):
        m = idx == i
        if m.sum() < 20:
            continue
        w = n[m]
        feats.append(np.concatenate([w.mean(axis=0) - ref, w.std(axis=0)]))
    return np.array(feats)


classes = {"bos": ["bos", "bos2"], "kapi": ["kapi"], "cam": ["cam"], "orta": ["orta"]}
names = list(classes)

train, test = {}, {}
for name, labels in classes.items():
    tr, te = [], []
    for lab in labels:
        f = windows(lab)
        half = len(f) // 2
        tr.append(f[:half])
        te.append(f[half:])
    train[name] = np.vstack(tr)
    test[name] = np.vstack(te)
    print(f"{name:5s}: egitim {len(train[name]):2d} pencere, test {len(test[name]):2d} pencere")

allx = np.vstack(list(train.values()))
mu, sd = allx.mean(axis=0), allx.std(axis=0) + 1e-9
cent = {n: ((train[n] - mu) / sd).mean(axis=0) for n in names}

conf = np.zeros((len(names), len(names)), dtype=int)
for i, n in enumerate(names):
    for x in (test[n] - mu) / sd:
        d = [np.linalg.norm(x - cent[m]) for m in names]
        conf[i, int(np.argmin(d))] += 1

print("\nKarisiklik tablosu (satir = gercek, sutun = tahmin)")
print("        " + " ".join(f"{n:>5s}" for n in names))
for i, n in enumerate(names):
    print(f"{n:>6s}: " + " ".join(f"{v:5d}" for v in conf[i]))

print(f"\nToplam dogruluk: {np.trace(conf) / conf.sum():.0%} ({np.trace(conf)}/{conf.sum()})")
print(f"Rastgele tahmin: {1 / len(names):.0%}")