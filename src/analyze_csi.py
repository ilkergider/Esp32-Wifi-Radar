"""
CSI ilk analiz: veri kalite raporu + isi haritasi + hareket skoru.

Kullanim (proje kokunden):
  pip install numpy matplotlib
  python src\\analyze_csi.py --yerlesim sagsol_v2

Girdi : data/metadata.csv ve data/raw/<yerlesim>/*.csv
Cikti : data/analysis/<yerlesim>/ klasoru (yerlesim verilmezse data/analysis/tum/)
          kalite_raporu.csv   (her kayit icin paket sayisi, hiz, RSSI, bozuk satir)
          isi_haritasi_ham.png (onceki yontem: kirpma ve paket normalizasyonu yok)
          isi_haritasi.png     (temizlenmis: bas/son kirpilmis, paket-normalize, kararsiz subcarrier'lar atilmis)
          fark_haritasi.png    (bos oda ortalama profiline gore yuzde fark; duran kisiyi gostermek icin)
          hareket_skoru.png    (senaryolara gore pencere bazli hareket skoru, kirpilmis veri)
          paket_hizi_rssi.png  (kayit basina paket hizi ve RSSI)

Temizlik adimlari (parametrelerle degistirilebilir):
  --kirp_bas 5   : her kaydin ilk 5 sn'si atilir (kisi yerine gecerken olusan hareket)
  --kirp_son 1   : son 1 sn atilir
  --kararsiz_kat 3 : degisim katsayisi medyanin 3 katini asan subcarrier'lar atilir
                     (blok sinirlarindaki bozuk subcarrier'lar, ~57 ve ~116 civari)
Tum isi haritalari sabit renk skalasi ve saniye cinsinden zaman ekseni kullanir.
"""
import argparse
import csv
import os
import sys
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# CSI_DATA satirinda data alanindan once 24 alan var (0..23), data 24. indekste
N_ONEK = 24
IDX_RSSI, IDX_LEN, IDX_FIRST_WORD = 3, 22, 23

SIRA = ["kisi0_bos_bos", "kisi1_sol_duran", "kisi1_orta_duran",
        "kisi1_sag_duran", "kisi1_gezen_hareket"]


def load_metadata(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.reader(f):
            if not r or r[0].strip() == "dosya" or len(r) < 8:
                continue
            try:
                sure = float(r[6])
            except ValueError:
                sure = 60.0
            rows.append({
                "dosya": r[0].strip(), "yerlesim": r[2].strip(),
                "kisi": r[3].strip(), "konum": r[4].strip(),
                "durum": r[5].strip(), "sure": sure,
            })
    return rows


def parse_file(path):
    """Bir CSV'yi okur. Doner: genlik matrisi (paket x subcarrier), rssi dizisi, toplam, bozuk."""
    amps, rssis = [], []
    toplam = bozuk = 0
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("CSI_DATA"):
                continue
            toplam += 1
            parts = line.split(",", N_ONEK)
            if len(parts) != N_ONEK + 1:
                bozuk += 1
                continue
            try:
                bildirilen = int(parts[IDX_LEN])
                first_word = int(parts[IDX_FIRST_WORD])
                veri = parts[N_ONEK].strip().strip('"').strip("[]")
                vals = np.array([int(x) for x in veri.split(",")], dtype=np.int16)
                if vals.size != bildirilen or vals.size % 2 != 0:
                    bozuk += 1
                    continue
                if first_word == 1:      # ilk 4 bayt donanim kaynakli gecersiz
                    vals[:4] = 0
                iq = vals.reshape(-1, 2).astype(np.float32)
                amps.append(np.hypot(iq[:, 0], iq[:, 1]))
                rssis.append(int(parts[IDX_RSSI]))
            except ValueError:
                bozuk += 1
    if not amps:
        return None, np.array([]), toplam, bozuk
    # farkli uzunlukta paketler varsa en yaygin uzunlugu tut
    uzunluk = Counter(len(a) for a in amps).most_common(1)[0][0]
    secili = [i for i, a in enumerate(amps) if len(a) == uzunluk]
    bozuk += len(amps) - len(secili)
    A = np.vstack([amps[i] for i in secili])
    R = np.array([rssis[i] for i in secili])
    return A, R, toplam, bozuk


def pencere_skorlari(A, valid, W, paket_norm=False):
    """Pencere basina hareket skoru: subcarrier'larin degisim katsayisi ortalamasi.
    paket_norm=True: her paketi kendi ortalama genligine boler (AGC/ortak kazanc oynamasini giderir)."""
    M = A[:, valid]
    if paket_norm:
        M = M / (M.mean(axis=1, keepdims=True) + 1e-6)
    n = M.shape[0] // W
    if n == 0:
        return np.array([])
    M = M[: n * W].reshape(n, W, -1)
    cv = M.std(axis=1) / (M.mean(axis=1) + 1e-6)
    return cv.mean(axis=1)


def paket_normalize(M):
    """Her paketi (satiri) kendi ortalama genligine boler: AGC kaynakli dikey cizgileri giderir."""
    return M / (M.mean(axis=1, keepdims=True) + 1e-6)


def kirp(v, bas_sn, son_sn, min_paket):
    """Kaydin basindan ve sonundan saniye cinsinden keser. Kalan cok kisaysa kirpmaz."""
    n = v["A"].shape[0]
    hiz = n / v["sure"]
    b = int(round(bas_sn * hiz))
    e = n - int(round(son_sn * hiz))
    if e - b < min_paket:
        print(f"UYARI: {v['dosya']} kirpilinca cok kisa kaliyor, kirpilmadi.")
        return v["A"], v["R"], 0.0
    return v["A"][b:e], v["R"][b:e], b / hiz


def isi_haritasi_ciz(paneller, yol, cmap, vmin, vmax, cbar_etiket, ust_baslik):
    """paneller: [(baslik, M (paket x subcarrier), paket_hizi, baslangic_sn)]"""
    fig, axes = plt.subplots(len(paneller), 1, figsize=(11, 2.2 * len(paneller) + 0.6),
                             constrained_layout=True)
    axes = np.atleast_1d(axes)
    sure_max = max(M.shape[0] / hiz + t0 for _, M, hiz, t0 in paneller)
    im = None
    for ax, (baslik, M, hiz, t0) in zip(axes, paneller):
        t1 = t0 + M.shape[0] / hiz
        im = ax.imshow(M.T, aspect="auto", origin="lower", cmap=cmap, vmin=vmin, vmax=vmax,
                       extent=[t0, t1, 0, M.shape[1]], interpolation="nearest")
        ax.set_xlim(0, sure_max)
        ax.set_title(baslik, fontsize=9)
        ax.set_ylabel("subcarrier\n(gecerli sira)", fontsize=8)
    axes[-1].set_xlabel("zaman (sn)")
    fig.colorbar(im, ax=axes, label=cbar_etiket, shrink=0.6, pad=0.01)
    fig.suptitle(ust_baslik, fontsize=10)
    fig.savefig(yol, dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="CSI ilk analiz")
    ap.add_argument("--veri_klasoru", default="data")
    ap.add_argument("--yerlesim", default=None,
                    help="Sadece bu oturumu analiz et, ornek: sagsol_v2 (varsayilan: hepsi)")
    ap.add_argument("--pencere", type=int, default=60,
                    help="Hareket skoru pencere boyu (paket sayisi), varsayilan 60 (~1 sn)")
    ap.add_argument("--kirp_bas", type=float, default=5.0,
                    help="Her kaydin basindan atilacak sure (sn), varsayilan 5")
    ap.add_argument("--kirp_son", type=float, default=1.0,
                    help="Her kaydin sonundan atilacak sure (sn), varsayilan 1")
    ap.add_argument("--kararsiz_kat", type=float, default=3.0,
                    help="Degisim katsayisi medyanin bu katini asan subcarrier atilir, varsayilan 3")
    a = ap.parse_args()

    meta_yol = os.path.join(a.veri_klasoru, "metadata.csv")
    if not os.path.exists(meta_yol):
        sys.exit(f"metadata.csv bulunamadi: {meta_yol}  (komutu proje kokunden calistir)")
    meta = load_metadata(meta_yol)
    if a.yerlesim:
        meta = [m for m in meta if m["yerlesim"] == a.yerlesim]
        if not meta:
            sys.exit(f"metadata.csv icinde '{a.yerlesim}' yerlesimi icin kayit yok.")
    cikti = os.path.join(a.veri_klasoru, "analysis", a.yerlesim or "tum")
    os.makedirs(cikti, exist_ok=True)

    # 1) Tum dosyalari oku
    veri = []
    for m in meta:
        yol = os.path.join(a.veri_klasoru, "raw", m["yerlesim"], m["dosya"])
        if not os.path.exists(yol):
            print(f"UYARI: dosya yok, atlandi: {yol}")
            continue
        A, R, toplam, bozuk = parse_file(yol)
        if A is None:
            print(f"UYARI: gecerli paket yok: {m['dosya']}")
            continue
        m = dict(m)
        m["senaryo"] = f"kisi{m['kisi']}_{m['konum']}_{m['durum']}"
        m.update(A=A, R=R, toplam=toplam, bozuk=bozuk)
        veri.append(m)
    if not veri:
        sys.exit("Okunacak veri yok.")

    # 2) Gecerli subcarrier'lar (sifir/null olanlari ele)
    S = Counter(v["A"].shape[1] for v in veri).most_common(1)[0][0]
    veri = [v for v in veri if v["A"].shape[1] == S]
    ortalama = np.mean([v["A"].mean(axis=0) for v in veri], axis=0)
    valid = ortalama > 1.0
    valid[:2] = False
    n_ilk = int(valid.sum())
    # a) ortalamasi digerlerine gore cok dusuk olanlari at (null/guard komsulari)
    valid &= ortalama > 0.2 * np.median(ortalama[valid])
    # b) kararsiz subcarrier'lari at: paket-normalize veride degisim katsayisi asiri yuksek olanlar
    #    (blok sinirlarinda gorulen ince parlak/koyu yatay cizgiler)
    tum = np.vstack([v["A"] for v in veri])
    Pn = np.zeros_like(tum)
    Pn[:, valid] = paket_normalize(tum[:, valid])
    cv_sc = Pn.std(axis=0) / (Pn.mean(axis=0) + 1e-6)
    esik_cv = a.kararsiz_kat * np.median(cv_sc[valid])
    kararsiz = valid & (cv_sc > esik_cv)
    valid &= ~kararsiz
    del tum, Pn
    print(f"\nPaket basina {S} subcarrier: sifir olmayan {n_ilk}, "
          f"kararsiz/zayif diye atilan {n_ilk - int(valid.sum())}, kalan {int(valid.sum())}.")
    if kararsiz.any():
        print(f"Kararsiz atilan subcarrier indeksleri: {np.flatnonzero(kararsiz).tolist()}")
    print()

    # 3) Kalite raporu
    baslik = ["dosya", "senaryo", "paket", "bozuk_satir", "hiz_pkt_sn", "rssi_ort", "rssi_min", "not"]
    rapor = []
    for v in veri:
        n = v["A"].shape[0]
        hiz = n / v["sure"]
        notlar = []
        if hiz < 40:
            notlar.append("DUSUK_HIZ")
        if v["R"].mean() < -75:
            notlar.append("ZAYIF_SINYAL")
        if v["bozuk"] > 0.02 * max(v["toplam"], 1):
            notlar.append("COK_BOZUK_SATIR")
        v["hiz"] = hiz
        rapor.append([v["dosya"], v["senaryo"], n, v["bozuk"], round(hiz, 1),
                      round(float(v["R"].mean()), 1), int(v["R"].min()), " ".join(notlar)])
    with open(os.path.join(cikti, "kalite_raporu.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(baslik)
        w.writerows(rapor)
    print("KALITE RAPORU")
    print(f"{'dosya':28s} {'paket':>6s} {'bozuk':>6s} {'hiz':>6s} {'rssi':>6s}  not")
    for r in rapor:
        print(f"{r[0]:28s} {r[2]:6d} {r[3]:6d} {r[4]:6.1f} {r[5]:6.1f}  {r[7]}")

    # 3b) Bas/son kirpma (kalite raporu ham veriyle yapildi, analiz kirpilmis veriyle)
    for v in veri:
        v["Ak"], v["Rk"], v["t0"] = kirp(v, a.kirp_bas, a.kirp_son, 2 * a.pencere)
    print(f"\nHer kayittan ilk {a.kirp_bas:g} sn ve son {a.kirp_son:g} sn atildi.")

    # 4) Senaryolara gore grupla
    gruplar = {}
    for v in veri:
        gruplar.setdefault(v["senaryo"], []).append(v)
    sirali = [s for s in SIRA if s in gruplar] + sorted(s for s in gruplar if s not in SIRA)
    bos_anahtar = next((s for s in sirali if "_bos_" in s or s.endswith("_bos")), None)

    # 5a) Isi haritasi, ONCE: eski yontem (kirpma yok, sadece subcarrier ortalamasina bolme)
    paneller = []
    for s in sirali:
        v = gruplar[s][0]
        M = v["A"][:, valid]
        M = M / (M.mean(axis=0, keepdims=True) + 1e-6)
        paneller.append((f"{s}  ({v['dosya']})", M, v["hiz"], 0.0))
    isi_haritasi_ciz(paneller, os.path.join(cikti, "isi_haritasi_ham.png"), "viridis", 0.5, 1.5,
                     "genlik / subcarrier ortalamasi",
                     "Ham: kirpma yok, paket normalizasyonu yok")

    # 5b) Isi haritasi, SONRA: kirpilmis + paket-normalize + kararsiz subcarrier'lar atilmis
    paneller = []
    for s in sirali:
        v = gruplar[s][0]
        M = paket_normalize(v["Ak"][:, valid])
        M = M / (M.mean(axis=0, keepdims=True) + 1e-6)
        paneller.append((f"{s}  ({v['dosya']})", M, v["hiz"], v["t0"]))
    isi_haritasi_ciz(paneller, os.path.join(cikti, "isi_haritasi.png"), "viridis", 0.7, 1.3,
                     "genlik / subcarrier ortalamasi",
                     f"Temizlenmis: ilk {a.kirp_bas:g} sn atildi, paket-normalize, "
                     f"{int(valid.sum())} gecerli subcarrier")

    # 5c) Fark haritasi: bos oda ortalama profiline gore yuzde fark
    #     Not: subcarrier'i kendi ortalamasina bolmek, duran kisinin kalici izini siler.
    #     Burada her kayit ayni bos-oda referansina bolunur, boylece kalici iz gorunur kalir.
    if bos_anahtar:
        bos_kayitlar = gruplar[bos_anahtar]
        # Gosterilen bos kaydi referansa katmamak icin, baska tekrar varsa onlari kullan
        ref_kaynak = bos_kayitlar[1:] if len(bos_kayitlar) > 1 else bos_kayitlar
        referans = np.mean([paket_normalize(v["Ak"][:, valid]).mean(axis=0) for v in ref_kaynak], axis=0)
        ref_adlari = ", ".join(v["dosya"] for v in ref_kaynak)
        paneller = []
        print("\nFARK HARITASI (bos oda referansina gore ortalama mutlak fark)")
        for s in sirali:
            v = gruplar[s][0]
            D = paket_normalize(v["Ak"][:, valid]) / (referans + 1e-6) - 1.0
            paneller.append((f"{s}  ({v['dosya']})", D * 100, v["hiz"], v["t0"]))
            print(f"{s:24s} ortalama |fark| = %{100 * np.abs(D).mean():.1f}")
        isi_haritasi_ciz(paneller, os.path.join(cikti, "fark_haritasi.png"), "RdBu_r", -40, 40,
                         "bos odaya gore fark (%)",
                         f"Fark haritasi: referans = {ref_adlari}  "
                         "(kirmizi: bos odadan guclu, mavi: zayif)")
        if len(bos_kayitlar) == 1:
            print("UYARI: tek bos kayit var; referans ayni kayittan alindi, bos panel yapay olarak temiz gorunur.")
    else:
        print("\nUYARI: bos oda kaydi bulunamadi, fark haritasi cizilmedi.")

    # 6) Hareket skoru (ham ve paket-normalize, kirpilmis veri)
    skor_ham = {s: np.concatenate([pencere_skorlari(v["Ak"], valid, a.pencere, False) for v in gruplar[s]])
                for s in sirali}
    skor_norm = {s: np.concatenate([pencere_skorlari(v["Ak"], valid, a.pencere, True) for v in gruplar[s]])
                 for s in sirali}
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.5))
    for ax, sk, baslik_ in zip(axs, (skor_ham, skor_norm), ("ham genlik", "paket-normalize genlik")):
        ax.boxplot([sk[s] for s in sirali])
        ax.set_xticks(range(1, len(sirali) + 1))
        ax.set_xticklabels([s.replace("kisi", "k") for s in sirali])
        ax.set_ylabel("hareket skoru (pencere basina)")
        ax.set_title(f"Hareket skoru: {baslik_}")
        plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(cikti, "hareket_skoru.png"), dpi=130)
    plt.close(fig)

    for ad, sk in (("HAM GENLIK", skor_ham), ("PAKET-NORMALIZE GENLIK", skor_norm)):
        print("\nHAREKET SKORU, %s (pencere = %d paket)" % (ad, a.pencere))
        esik = np.percentile(sk[bos_anahtar], 95) if bos_anahtar else None
        for s in sirali:
            satir = f"{s:24s} medyan={np.median(sk[s]):.4f}  pencere={len(sk[s])}"
            if esik is not None and s != bos_anahtar:
                satir += f"  bos p95 esiginin ustunde: %{100 * np.mean(sk[s] > esik):.0f}"
            print(satir)

    # 7) Paket hizi ve RSSI
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    adlar = [v["dosya"].replace(".csv", "") for v in veri]
    ax1.bar(range(len(veri)), [v["hiz"] for v in veri])
    ax1.set_ylabel("paket/sn")
    ax2.bar(range(len(veri)), [float(v["R"].mean()) for v in veri], color="tab:orange")
    ax2.set_ylabel("RSSI ort. (dBm)")
    ax2.set_xticks(range(len(veri)))
    ax2.set_xticklabels(adlar, rotation=60, ha="right", fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(cikti, "paket_hizi_rssi.png"), dpi=130)
    plt.close(fig)

    print(f"\nCiktilar: {cikti}")


if __name__ == "__main__":
    main()
