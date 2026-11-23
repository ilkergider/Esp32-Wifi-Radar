"""
Canli RSSI ve paket hizi izleyici (kurulum/yerlesim ayari icin, veri kaydetmez).

Kullanim:
  python src\\rssi_monitor.py COM8
  python src\\rssi_monitor.py COM8 --baud 921600

Her saniye: paket/sn ve RSSI (ortalama, min, max). Kartlari tasirken izle.
Hedef: RSSI -65 dBm veya daha iyisi (ornek: -55). Durdurmak icin Ctrl+C.
"""
import argparse
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial yok. Kur: pip install pyserial")


def seviye(r):
    if r >= -65:
        return "IYI"
    if r >= -75:
        return "ORTA"
    return "ZAYIF"


def main():
    p = argparse.ArgumentParser(description="Canli RSSI izleyici")
    p.add_argument("port", help="Alici ESP32 portu, ornek: COM8")
    p.add_argument("--baud", type=int, default=921600)
    a = p.parse_args()

    try:
        ser = serial.Serial(a.port, a.baud, timeout=1)
    except serial.SerialException as e:
        sys.exit(f"Port acilamadi ({a.port}): {e}")

    print(f"{a.port} dinleniyor. Durdurmak icin Ctrl+C.\n")
    print(f"{'paket/sn':>9s} {'rssi_ort':>9s} {'min':>5s} {'max':>5s}  durum")
    ser.reset_input_buffer()
    rssiler = []
    t0 = time.time()
    try:
        while True:
            ham = ser.readline()
            if ham:
                satir = ham.decode("utf-8", errors="ignore").strip()
                if satir.startswith("CSI_DATA"):
                    parts = satir.split(",", 4)
                    try:
                        rssiler.append(int(parts[3]))
                    except (ValueError, IndexError):
                        pass
            simdi = time.time()
            if simdi - t0 >= 1:
                if rssiler:
                    ort = sum(rssiler) / len(rssiler)
                    print(f"{len(rssiler) / (simdi - t0):9.1f} {ort:9.1f} {min(rssiler):5d} "
                          f"{max(rssiler):5d}  {seviye(ort)}")
                else:
                    print(f"{0:9.1f} {'-':>9s} {'-':>5s} {'-':>5s}  PAKET YOK")
                rssiler = []
                t0 = simdi
    except KeyboardInterrupt:
        print("\nDurduruldu.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
