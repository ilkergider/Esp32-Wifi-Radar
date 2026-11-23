"""
CSI veri kaydedici (ESP32 alici -> seri port -> CSV)

Ornek kullanim (proje kokunden):
  python src\\serial_logger.py COM10 --kisi 0 --konum bos --durum bos
  python src\\serial_logger.py COM10 --kisi 1 --konum sol --durum duran
  python src\\serial_logger.py COM10 --kisi 1 --konum gezen --durum hareket --sure 90

Her kayit:
  - 'gecikme' saniye geri sayim yapar (odadan cikip kapiyi kapatman icin)
  - data/raw/<yerlesim>/ altina otomatik numarali dosya yazar
  - data/metadata.csv dosyasina bir satir ekler
"""
import argparse
import csv
import os
import sys
import time
from datetime import datetime

try:
    import serial
except ImportError:
    sys.exit("pyserial yok. Kur: pip install pyserial")

try:
    import winsound  # sadece Windows
except ImportError:
    winsound = None

METADATA_BASLIK = [
    "dosya", "tarih_saat", "yerlesim", "kisi_sayisi", "konum",
    "durum", "sure_sn", "satir_sayisi", "not",
]


def bip(frekans=1000, ms=200):
    if winsound:
        winsound.Beep(frekans, ms)
    else:
        print("\a", end="", flush=True)


def siradaki_dosya_adi(klasor, onek):
    """kisi1_sol_duran_01.csv, _02.csv ... seklinde ilk bos numarayi bulur."""
    n = 1
    while os.path.exists(os.path.join(klasor, f"{onek}_{n:02d}.csv")):
        n += 1
    return f"{onek}_{n:02d}.csv"


def metadata_ekle(yol, satir):
    yeni = not os.path.exists(yol)
    with open(yol, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if yeni:
            w.writerow(METADATA_BASLIK)
        w.writerow(satir)


def geri_sayim(saniye, mesaj):
    for kalan in range(saniye, 0, -1):
        print(f"\r{mesaj} {kalan:2d} sn ...", end="", flush=True)
        if kalan <= 3:
            bip(800, 120)
        time.sleep(1)
    print("\r" + " " * 60 + "\r", end="")


def main():
    p = argparse.ArgumentParser(description="ESP32 CSI veri kaydedici")
    p.add_argument("port", help="Alici ESP32 portu, ornek: COM10")
    p.add_argument("--kisi", type=int, required=True, help="Odadaki kisi sayisi (0,1,2,...)")
    p.add_argument("--konum", required=True,
                   help="bos / sol / orta / sag / gezen gibi serbest etiket")
    p.add_argument("--durum", required=True,
                   help="bos / duran / hareket gibi serbest etiket")
    p.add_argument("--sure", type=int, default=60, help="Kayit suresi (sn), varsayilan 60")
    p.add_argument("--gecikme", type=int, default=10,
                   help="Baslamadan once geri sayim (sn), varsayilan 10")
    p.add_argument("--yerlesim", default="sagsol_v1", help="ESP32 yerlesim adi")
    p.add_argument("--baud", type=int, default=921600,
                   help="Baud hizi (eski kodunda ne kullandiysan onu yaz)")
    p.add_argument("--not", dest="notu", default="", help="Metadata'ya yazilacak kisa not")
    p.add_argument("--veri_klasoru", default="data", help="Veri klasoru (varsayilan: data)")
    a = p.parse_args()

    klasor = os.path.join(a.veri_klasoru, "raw", a.yerlesim)
    os.makedirs(klasor, exist_ok=True)

    onek = f"kisi{a.kisi}_{a.konum}_{a.durum}"
    dosya_adi = siradaki_dosya_adi(klasor, onek)
    dosya_yolu = os.path.join(klasor, dosya_adi)

    try:
        ser = serial.Serial(a.port, a.baud, timeout=1)
    except serial.SerialException as e:
        sys.exit(f"Port acilamadi ({a.port}): {e}\n"
                 "Baska bir program (ESP-IDF monitor vb.) portu tutuyor olabilir.")

    print(f"Kayit: {dosya_adi}  |  {a.sure} sn  |  port {a.port}")
    ser.reset_input_buffer()

    if a.gecikme > 0:
        geri_sayim(a.gecikme, "Baslamasina")

    print("KAYIT BASLADI")
    bip(1500, 400)

    satir_sayisi = 0
    baslangic = time.time()
    son_yazdirma = baslangic
    yarida_kesildi = False

    try:
        with open(dosya_yolu, "w", encoding="utf-8", newline="") as f:
            while time.time() - baslangic < a.sure:
                try:
                    ham = ser.readline()
                except serial.SerialException as e:
                    print(f"\nSeri port hatasi: {e}")
                    yarida_kesildi = True
                    break
                if not ham:
                    continue
                satir = ham.decode("utf-8", errors="ignore").strip()
                if satir.startswith("CSI_DATA"):
                    f.write(satir + "\n")
                    satir_sayisi += 1

                simdi = time.time()
                if simdi - son_yazdirma >= 1:
                    gecen = int(simdi - baslangic)
                    print(f"\r  {gecen:3d}/{a.sure} sn  |  {satir_sayisi} paket",
                          end="", flush=True)
                    son_yazdirma = simdi
    except KeyboardInterrupt:
        yarida_kesildi = True
        print("\nCtrl+C ile durduruldu, o ana kadarki veri kaydedildi.")
    finally:
        ser.close()

    gercek_sure = round(time.time() - baslangic)
    bip(1500, 400)
    print(f"\nBITTI: {dosya_yolu}  ({satir_sayisi} paket, {gercek_sure} sn)")

    if satir_sayisi == 0:
        print("UYARI: hic CSI_DATA satiri gelmedi. Port, baud hizi ve verici acik mi kontrol et.")
    elif satir_sayisi < gercek_sure * 5:
        print("UYARI: paket sayisi cok dusuk. Verici calisiyor mu, kartlar birbirini goruyor mu?")

    not_metni = a.notu + (" | yarida kesildi" if yarida_kesildi else "")
    metadata_ekle(
        os.path.join(a.veri_klasoru, "metadata.csv"),
        [
            dosya_adi,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            a.yerlesim, a.kisi, a.konum, a.durum,
            gercek_sure, satir_sayisi, not_metni.strip(" |"),
        ],
    )


if __name__ == "__main__":
    main()
