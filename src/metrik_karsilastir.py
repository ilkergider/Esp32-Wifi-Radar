"""
Hareket metriklerini karsilastirir: hangi hesaplama bos oda ile hareketi ayirabiliyor?

Kullanim (proje kokunden, analyze_csi.py ile ayni klasorde):
  python src\\metrik_karsilastir.py --yerlesim sagsol_v2
  python src\\metrik_karsilastir.py --yerlesim sagsol_v2 --pencere 200

Her metrik icin, bos odanin pencere skorlarinin %95'lik esiginin ustune cikan pencere
orani (%) yazdirilir. Bos satirda bu oran ~%5 olur (yanlis alarm). Diger satirlarda
yuksek oran = o metrik o senaryoyu bos odadan ayirabiliyor demek.
Cikti: data/analysis/<yerlesim>/zaman_serisi.png
"""
import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import analyze_csi as ac  # ayni klasordeki analyze_csi.py

METRIKLER = ["cv_ham", "cv_ust", "cv_yumusak", "ortgenlik", "bant", "korelasyon"]
ACIKLAMA = {
    "cv_ham": "subcarrier basina degisim katsayisi (onceki skor)",
    "cv_ust": "ayni, sadece guclu subcarrier'lar",
    "cv_yumusak": "zamanda yumusatilmis + guclu subcarrier'lar",
    "ortgenlik": "tum subcarrier ortalamasi sinyalinin degisimi",
    "bant": "ortalama sinyalin 0.3-5 Hz bant enerjisi",
    "korelasyon": "ardisik paketler arasi spektrum sekli degisimi (1 - korelasyon)",
}


def pencereler(X, W):
    n = X.shape[0] // W
    return X[: n * W].reshape(n, W, -1)


def cv(X, W):
    P = pencereler(X, W)
    if P.shape[0] == 0:
        return np.array([])
    return (P.std(axis=1) / (P.mean(axis=1) + 1e-6)).mean(axis=1)


def hareketli_ort(X, k):
    c = np.cumsum(np.pad(X, ((1, 0), (0, 0))), axis=0)
    return (c[k:] - c[:-k]) / k


def metrikler(A, valid, ust, W, fs):
    X = A[:, valid]
    Xu = X[:, ust]
    m = X.mean(axis=1, keepdims=True)
    sonuc = {}
    sonuc["cv_ham"] = cv(X, W)
    sonuc["cv_ust"] = cv(Xu, W)
    sonuc["cv_yumusak"] = cv(hareketli_ort(Xu, 9), W)
    sonuc["ortgenlik"] = cv(m, W)

    Pm = pencereler(m, W)[:, :, 0]
    if Pm.shape[0] > 0:
        ort = Pm.mean(axis=1)
        P = (Pm - ort[:, None]) * np.hanning(W)
        F = np.abs(np.fft.rfft(P, axis=1)) ** 2
        f = np.fft.rfftfreq(W, d=1.0 / fs)
        bant = (f >= 0.3) & (f <= 5.0)
        sonuc["bant"] = np.sqrt(F[:, bant].sum(axis=1)) / (W * ort + 1e-6)
    else:
        sonuc["bant"] = np.array([])

    Z = (Xu - Xu.mean(axis=1, keepdims=True)) / (Xu.std(axis=1, keepdims=True) + 1e-6)
    d = 5
    c = (Z[:-d] * Z[d:]).mean(axis=1)
    n = c.shape[0] // W
    sonuc["korelasyon"] = 1 - c[: n * W].reshape(n, W).mean(axis=1) if n > 0 else np.array([])
    return sonuc


def main():
    ap = argparse.ArgumentParser(description="Hareket metriklerini karsilastir")
    ap.add_argument("--veri_klasoru", default="data")
    ap.add_argument("--yerlesim", required=True, help="Oturum adi, ornek: sagsol_v2")
    ap.add_argument("--pencere", type=int, default=200,
                    help="Pencere boyu (paket), varsayilan 200 (~3 sn)")
    a = ap.parse_args()

    meta = [m for m in ac.load_metadata(os.path.join(a.veri_klasoru, "metadata.csv"))
            if m["yerlesim"] == a.yerlesim]
    if not meta:
        sys.exit(f"metadata.csv icinde '{a.yerlesim}' icin kayit yok.")

    veri = []
    for m in meta:
        yol = os.path.join(a.veri_klasoru, "raw", m["yerlesim"], m["dosya"])
        if not os.path.exists(yol):
            continue
        A, R, toplam, bozuk = ac.parse_file(yol)
        if A is None:
            continue
        m = dict(m)
        m["senaryo"] = f"kisi{m['kisi']}_{m['konum']}_{m['durum']}"
        m["A"] = A
        m["fs"] = A.shape[0] / m["sure"]
        m["rssi"] = float(R.mean())
        veri.append(m)
    if not veri:
        sys.exit("Okunacak veri yok.")

    S = max(set(v["A"].shape[1] for v in veri), key=[v["A"].shape[1] for v in veri].count)
    veri = [v for v in veri if v["A"].shape[1] == S]
    ortalama = np.mean([v["A"].mean(axis=0) for v in veri], axis=0)
    valid = ortalama > 1.0
    valid[:2] = False
    ort_valid = ortalama[valid]
    ust = ort_valid >= np.median(ort_valid)

    gruplar = {}
    for v in veri:
        gruplar.setdefault(v["senaryo"], []).append(v)
    sirali = [s for s in ac.SIRA if s in gruplar] + sorted(s for s in gruplar if s not in ac.SIRA)

    skor = {s: {k: [] for k in METRIKLER} for s in sirali}
    for s in sirali:
        for v in gruplar[s]:
            r = metrikler(v["A"], valid, ust, a.pencere, v["fs"])
            for k in METRIKLER:
                skor[s][k].append(r[k])
        for k in METRIKLER:
            skor[s][k] = np.concatenate(skor[s][k])

    bos = next((s for s in sirali if s.endswith("_bos")), None)
    print(f"\nPencere = {a.pencere} paket. Deger: bos odanin %95 esiginin ustundeki pencere orani (%)")
    print("Bos satirinda ~%5 normaldir (yanlis alarm). Yuksek deger = ayirabiliyor.\n")
    print(f"{'senaryo':24s}" + "".join(f"{k:>12s}" for k in METRIKLER))
    esik = {k: np.percentile(skor[bos][k], 95) for k in METRIKLER}
    for s in sirali:
        satir = f"{s:24s}"
        for k in METRIKLER:
            satir += f"{100 * np.mean(skor[s][k] > esik[k]):11.0f}%"
        print(satir)
    print("\nMetrikler:")
    for k in METRIKLER:
        print(f"  {k:12s} {ACIKLAMA[k]}")

    print("\nORTALAMA RSSI (dBm), senaryo bazinda:")
    for s_ in sirali:
        print(f"  {s_:24s} {np.mean([v['rssi'] for v in gruplar[s_]]):.1f}")

    # Zaman serisi grafigi: her senaryodan ilk kayit, ortalama genlik
    cikti = os.path.join(a.veri_klasoru, "analysis", a.yerlesim)
    os.makedirs(cikti, exist_ok=True)
    fig, axes = plt.subplots(len(sirali), 1, figsize=(11, 2.0 * len(sirali)), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, s in zip(axes, sirali):
        v = gruplar[s][0]
        m = v["A"][:, valid].mean(axis=1)
        m = m / m.mean()
        k = 15
        ms = np.convolve(m, np.ones(k) / k, mode="valid")
        ax.plot(m, color="lightgray", lw=0.5)
        ax.plot(np.arange(len(ms)) + k // 2, ms, color="tab:blue", lw=1)
        ax.set_title(f"{s} ({v['dosya']})", fontsize=9)
        ax.set_ylabel("ort. genlik")
    axes[-1].set_xlabel("paket sirasi")
    fig.tight_layout()
    fig.savefig(os.path.join(cikti, "zaman_serisi.png"), dpi=130)
    plt.close(fig)
    print(f"\nGrafik: {os.path.join(cikti, 'zaman_serisi.png')}")


if __name__ == "__main__":
    main()
