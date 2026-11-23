"""CSI kayitlarini karsilastirir: bos vs hareketli (v2).

Kullanim (proje klasorunden):
    python src\analyze.py
    python src\analyze.py bos hareketli      # etiketleri degistirmek icin

v2: paket basina normalizasyon (gain dalgalanmasini giderir),
    2 sn pencere, iki hareket olcusu: 'std' ve 'corr'.
"""
import csv
import glob
import os
import re
import sys

import numpy as np
import matplotlib.pyplot as plt

SKIP_SEC = 10        # kaydin ilk kismi atilir
WIN_SEC = 2.0        # hareket skoru pencere uzunlugu
DATA_DIR = "data"


def latest_file(label):
    files = sorted(glob.glob(os.path.join(DATA_DIR, f"{label}_*.csv")))
    if not files:
        sys.exit(f"'{label}_*.csv' bulunamadi ({DATA_DIR} klasorunde)")
    return files[-1]


def load(path):
    """Her satirdan (zaman_sn, genlik[alt_tasiyici]) cikarir."""
    times, amps = [], []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "CSI_DATA" not in line:
                continue
            m = re.search(r"\[([^\]]+)\]", line)
            if not m:
                continue
            try:
                raw = np.array([int(x) for x in re.split(r"[,\s]+", m.group(1).strip())
                                if x.lstrip("-").isdigit()])
            except ValueError:
                continue
            if len(raw) < 2 or len(raw) % 2:
                continue
            # ESP32 CSI sirasi: imag, real, imag, real ...
            imag, real = raw[0::2], raw[1::2]
            amp = np.sqrt(real.astype(float) ** 2 + imag.astype(float) ** 2)

            ts = None
            head = line[: m.start()]
            try:
                fields = next(csv.reader([head]))
                i = fields.index("CSI_DATA")
                ts = int(fields[i + 18]) / 1e6
            except Exception:
                pass
            times.append(ts)
            amps.append(amp)

    if not amps:
        sys.exit(f"{path}: gecerli CSI satiri yok")

    lens = [len(a) for a in amps]
    common = max(set(lens), key=lens.count)
    keep = [i for i, l in enumerate(lens) if l == common]
    amps = np.array([amps[i] for i in keep])
    times = [times[i] for i in keep]

    if any(t is None for t in times):
        t = np.linspace(0, 45, len(amps))
        print(f"  uyari: {os.path.basename(path)} zaman damgasi okunamadi, "
            f"sure 45 sn varsayildi")
    else:
        t = np.array(times) - times[0]
    return t, amps


def normalize(amps):
    """Null alt tasiyicilari at, her paketi kendi ortalamasina bol."""
    live = amps.std(axis=0) > 0
    a = amps[:, live]
    return a / a.mean(axis=1, keepdims=True)


def window_scores(t, a):
    """Her pencere icin iki olcu: std (zamansal dalgalanma), corr (1 - ardisik paket korelasyonu)."""
    starts = np.arange(0, t[-1] - WIN_SEC, WIN_SEC / 2)
    ct, s_std, s_corr = [], [], []
    for s in starts:
        sel = (t >= s) & (t < s + WIN_SEC)
        if sel.sum() < 8:
            continue
        w = a[sel]
        ct.append(s + WIN_SEC / 2)
        s_std.append(w.std(axis=0).mean())
        wc = w - w.mean(axis=1, keepdims=True)
        wc /= np.linalg.norm(wc, axis=1, keepdims=True) + 1e-12
        c = (wc[:-1] * wc[1:]).sum(axis=1)
        s_corr.append(1 - c.mean())
    return np.array(ct), {"std": np.array(s_std), "corr": np.array(s_corr)}


def evaluate(b, h):
    thr = (np.percentile(b, 95) + np.median(h)) / 2
    return thr, (b < thr).mean() * 100, (h >= thr).mean() * 100


def main():
    labels = sys.argv[1:3] or ["bos", "hareketli"]
    data = {}
    for lb in labels:
        path = latest_file(lb)
        t, amps = load(path)
        keep = t >= SKIP_SEC
        t, amps = t[keep] - SKIP_SEC, amps[keep]
        rate = len(t) / max(t[-1], 1e-9)
        print(f"{lb}: {os.path.basename(path)} | {len(t)} paket | ~{rate:.0f} paket/sn")
        a = normalize(amps)
        ct, sc = window_scores(t, a)
        data[lb] = (t, a, ct, sc)

    print()
    thr = {}
    for name in ("std", "corr"):
        b, h = data[labels[0]][3][name], data[labels[1]][3][name]
        thr[name], acc_b, acc_h = evaluate(b, h)
        print(f"[{name}] {labels[0]}: ort {b.mean():.4f}, maks {b.max():.4f} | "
            f"{labels[1]}: ort {h.mean():.4f}, min {h.min():.4f}")
        print(f"[{name}] esik {thr[name]:.4f} -> {labels[0]} %{acc_b:.0f}, "
            f"{labels[1]} %{acc_h:.0f} dogru")

    fig, ax = plt.subplots(3, 2, figsize=(13, 9))
    for j, lb in enumerate(labels):
        t, a, ct, sc = data[lb]
        im = ax[0, j].imshow(a.T, aspect="auto", origin="lower",
                            extent=[0, t[-1], 0, a.shape[1]], cmap="inferno")
        ax[0, j].set_title(f"{lb}: normalize genlik")
        ax[0, j].set_xlabel("sn"); ax[0, j].set_ylabel("alt tasiyici")
        fig.colorbar(im, ax=ax[0, j])
        for r, name in enumerate(("std", "corr"), start=1):
            ax[r, j].plot(ct, sc[name])
            ax[r, j].axhline(thr[name], color="r", ls="--", label=f"esik {thr[name]:.3f}")
            ax[r, j].set_title(f"{lb}: skor [{name}]")
            ax[r, j].set_xlabel("sn"); ax[r, j].legend()
    fig.tight_layout()
    out = os.path.join(DATA_DIR, "analiz.png")
    fig.savefig(out, dpi=130)
    print(f"\nGrafik kaydedildi: {out}")
    plt.show()


if __name__ == "__main__":
    main()