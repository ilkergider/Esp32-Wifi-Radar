import time
import numpy as np
from csi_processor import parse_csi_raw, butter_lowpass_filter
from visualizer import HeatmapVisualizer

def main():
    print("==========================================")
    print(" Wi-Fi CSI Varlık ve Hareket Takip Sistemi")
    print("==========================================")
    
    # 5x5 metrelik bir oda için görselleştiriciyi başlat
    visualizer = HeatmapVisualizer(room_size=(5, 5))
    
    print("[BİLGİ] Sistem dinleniyor (Simülasyon Modu)...")
    
    try:
        while True:
            # 1. ESP32'den gelen veriyi taklit et (Dummy CSI Verisi)
            dummy_raw_csi = np.random.randint(-128, 127, size=128)
            
            # 2. Sinyali temizle ve genliği hesapla
            amplitudes = parse_csi_raw(dummy_raw_csi)
            
            # 3. Hareketin şiddetine göre konum üret (Test amaçlı)
            signal_variance = np.var(amplitudes)
            x_pos = 2.5 + np.sin(time.time()) * 1.5
            y_pos = 2.5 + np.cos(time.time()) * 1.5
            
            # 4. Isı haritasını güncelle
            visualizer.update_heatmap(target_pos=(x_pos, y_pos), intensity=min(1.0, signal_variance / 5000))
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n[BİLGİ] Sistem kullanıcı tarafından durduruldu.")

if __name__ == "__main__":
    main()