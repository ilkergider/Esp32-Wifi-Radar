"""
Siniflandirma denemesi: pencere ozellikleri -> senaryo / bos-dolu.
Dogrulama: "bir tekrari disarida birak" (ornek: _01 ve _02 ile egit, _03 ile test et).

Kullanim (proje kokunden, analyze_csi.py ile ayni klasorde):
  pip install scikit-learn
  python src\\siniflandir_denemesi.py --yerlesim sagsol_v2
  python src\\siniflandir_denemesi.py --yerlesim sagsol_v2 --pencere 150

Ozellik setleri:
  rssi          : pencerenin ortalama RSSI degeri (tek sayi, referans)
  seviye        : subcarrier basina ortalama genlik profili (sabit duran kisiyi gormek icin)
  seviye+degisim: seviye + subcarrier basina degisim (hareketi de gormek icin)
"""
import argparse
import os
import sys

import numpy as np

import analyze_csi as ac  # ayni klasordeki analyze_csi.py

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import balanced_accuracy_score, confusion_matrix
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
except ImportError:
    sys.exit("scikit-learn yok. Kur: pip install scikit-learn")


def pencere_ozellikleri(A, R, valid, W):
    X = A[:, valid]
    n = X.shape[0] // W
    if n == 0:
        return None
    P = X[: n * W].reshape(n, W, -1)
    r = R[: n * W].reshape(n, W).mean(axis=1)
    ort = P.mean(axis=1)
    ort = ort / (ort.mean(axis=1, keepdims=True) + 1e-6)   # ortak kazanc farkini gider
    degisim = P.std(axis=1) / (P.mean(axis=1) + 1e-6)
    return ort, degisim, r[:, None]


def modeller():
    return {
        "RandomForest": lambda: RandomForestClassifier(
            n_estimators=200, class_weight="balanced", random_state=0, n_jobs=-1),
        "SVM": lambda: make_pipeline(
            StandardScaler(), SVC(kernel="rbf", C=1.0, class_weight="balanced")),
    }


def capraz_dogrula(X, y, gruplar, model_fabrikasi):
    tahmin = np.empty(len(y), dtype=object)
    for g in np.unique(gruplar):
        egit = gruplar != g
        test = gruplar == g
        m = model_fabrikasi()
        m.fit(X[egit], y[egit])
        tahmin[test] = m.predict(X[test])
    return tahmin


def main():
    ap = argparse.ArgumentParser(description="Siniflandirma denemesi")
    ap.add_argument("--veri_klasoru", default="data")
    ap.add_argument("--yerlesim", required=True, help="Oturum adi, ornek: sagsol_v2")
    ap.add_argument("--pencere", type=int, default=100,
                    help="Pencere boyu (paket), varsayilan 100 (~1.5 sn)")
    a = ap.parse_args()

    meta = [m for m in ac.load_metadata(os.path.join(a.veri_klasoru, "metadata.csv"))
            if m["yerlesim"] == a.yerlesim]
    if not meta:
        sys.exit(f"metadata.csv icinde '{a.yerlesim}' icin kayit yok.")

    kayitlar = []
    for m in meta:
        yol = os.path.join(a.veri_klasoru, "raw", m["yerlesim"], m["dosya"])
        if not os.path.exists(yol):
            continue
        A, R, _, _ = ac.parse_file(yol)
        if A is None:
            continue
        m = dict(m)
        m["senaryo"] = f"kisi{m['kisi']}_{m['konum']}_{m['durum']}"
        try:
            m["tekrar"] = int(m["dosya"].rsplit("_", 1)[1].split(".")[0])
        except (IndexError, ValueError):
            m["tekrar"] = 0
        m["A"], m["R"] = A, R
        kayitlar.append(m)
    if not kayitlar:
        sys.exit("Okunacak veri yok.")

    S = max(set(k["A"].shape[1] for k in kayitlar), key=[k["A"].shape[1] for k in kayitlar].count)
    kayitlar = [k for k in kayitlar if k["A"].shape[1] == S]
    ortalama = np.mean([k["A"].mean(axis=0) for k in kayitlar], axis=0)
    valid = ortalama > 1.0
    valid[:2] = False

    Xo, Xd, Xr, y, g = [], [], [], [], []
    for k in kayitlar:
        o = pencere_ozellikleri(k["A"], k["R"], valid, a.pencere)
        if o is None:
            continue
        ort, deg, r = o
        Xo.append(ort); Xd.append(deg); Xr.append(r)
        y += [k["senaryo"]] * len(ort)
        g += [k["tekrar"]] * len(ort)
    Xo, Xd, Xr = np.vstack(Xo), np.vstack(Xd), np.vstack(Xr)
    y, g = np.array(y, dtype=object), np.array(g)
    if len(np.unique(g)) < 2:
        sys.exit("Capraz dogrulama icin en az 2 farkli tekrar (_01, _02, ...) gerekli.")

    ozellik_setleri = {
        "rssi": Xr,
        "seviye": Xo,
        "seviye+degisim": np.hstack([Xo, Xd]),
    }
    gorevler = {
        "5 sinif": y,
        "bos/dolu": np.array(["bos" if s.endswith("_bos") else "dolu" for s in y], dtype=object),
    }
    siniflar5 = [s for s in ac.SIRA if s in set(y)] + sorted(set(y) - set(ac.SIRA))

    print(f"\n{len(y)} pencere ({a.pencere} paket), {len(np.unique(g))} tekrar, "
          f"dogrulama: bir tekrari disarida birak")
    print("Rastgele tahmin (dengeli dogruluk): 5 sinif = %20, bos/dolu = %50\n")
    print(f"{'ozellik':16s} {'model':13s} {'gorev':9s} {'dogruluk':>9s} {'dengeli':>9s}")
    en_iyi = (-1, None)
    for oz_ad, X in ozellik_setleri.items():
        for m_ad, fab in modeller().items():
            for gorev, yy in gorevler.items():
                tahmin = capraz_dogrula(X, yy, g, fab)
                dogru = np.mean(tahmin == yy)
                dengeli = balanced_accuracy_score(yy, tahmin)
                print(f"{oz_ad:16s} {m_ad:13s} {gorev:9s} {100 * dogru:8.0f}% {100 * dengeli:8.0f}%")
                if gorev == "5 sinif" and dengeli > en_iyi[0]:
                    en_iyi = (dengeli, (oz_ad, m_ad, tahmin))

    oz_ad, m_ad, tahmin = en_iyi[1]
    print(f"\nEn iyi 5 sinif sonucu: {oz_ad} + {m_ad}. Karisiklik matrisi (satir = gercek, sutun = tahmin):")
    cm = confusion_matrix(y, tahmin, labels=siniflar5)
    kisa = [s.replace("kisi", "k")[:14] for s in siniflar5]
    print(f"{'':16s}" + "".join(f"{k:>15s}" for k in kisa))
    for ad, satir in zip(kisa, cm):
        print(f"{ad:16s}" + "".join(f"{v:15d}" for v in satir))

    print("\nNOT: Tekrarlar ayni oturumda ardisik cekildigi icin bu sonuc iyimser olabilir.")
    print("Asil sinav: baska bir gun/saatte kayit alip onunla test etmek.")


if __name__ == "__main__":
    main()
