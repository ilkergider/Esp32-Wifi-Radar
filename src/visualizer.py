import numpy as np
import matplotlib.pyplot as plt

class HeatmapVisualizer:
    def __init__(self, room_size=(5, 5), grid_resolution=50):
        """
        Oda boyutları ve çözünürlük ayarları.
        room_size: Odanın (genişlik, uzunluk) metre cinsinden boyutu.
        grid_resolution: Haritadaki kare sayısı (çözünürlük).
        """
        self.room_size = room_size
        self.grid_res = grid_resolution
        
        # Grafik pencerelerini başlatma
        plt.ion()  # Interaktif mod (canlı güncelleme için)
        self.fig, self.ax = plt.subplots(figsize=(6, 6))
        
        # Grid (Izgara) koordinatlarını oluşturma
        self.x = np.linspace(0, room_size[0], grid_resolution)
        self.y = np.linspace(0, room_size[1], grid_resolution)
        self.X, self.Y = np.meshgrid(self.x, self.y)
        
        # Başlangıçta boş bir ısı haritası matrisi
        self.heatmap_data = np.zeros((grid_resolution, grid_resolution))
        
        # Renk haritası (Hot: Mavi -> Sarı -> Kırmızı)
        self.im = self.ax.imshow(
            self.heatmap_data, 
            extent=[0, room_size[0], 0, room_size[1]], 
            origin='lower', 
            cmap='hot', 
            interpolation='gaussian',
            vmin=0, vmax=1
        )
        
        self.fig.colorbar(self.im, ax=self.ax, label='Hareket / Yoğunluk Seviyesi')
        self.ax.set_title('Wi-Fi CSI Tabanlı Canlı İç Mekan Isı Haritası')
        self.ax.set_xlabel('Genişlik (Metre)')
        self.ax.set_ylabel('Uzunluk (Metre)')
        self.ax.grid(True, linestyle='--', alpha=0.3)

    def update_heatmap(self, target_pos, intensity=0.8):
        """
        İnsanın tespit edildiği konuma (X, Y) göre ısı haritasını günceller.
        target_pos: (x, y) metre cinsinden insan konumu.
        """
        tx, ty = target_pos
        
        # 2D Gauss dağılımı ile insanın bulunduğu noktada kırmızı leke (ısı) oluşturma
        sigma = 0.6  # Isı lekesinin yayılma yarıçapı
        gaussian_spot = np.exp(-((self.X - tx)**2 + (self.Y - ty)**2) / (2 * sigma**2))
        
        self.heatmap_data = gaussian_spot * intensity
        
        # Grafiği güncelle
        self.im.set_data(self.heatmap_data)
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

# ==========================================
# TEST / SİMÜLASYON (ESP32 Yokken Çalıştırmak İçin)
# ==========================================
if __name__ == "__main__":
    import time
    
    print("Isı haritası simülasyonu başlatılıyor...")
    vis = HeatmapVisualizer(room_size=(5, 5))
    
    # Oda içinde rastgele yürüyen bir insan simülasyonu
    for _ in range(30):
        fake_x = np.random.uniform(1.0, 4.0)
        fake_y = np.random.uniform(1.0, 4.0)
        
        vis.update_heatmap(target_pos=(fake_x, fake_y))
        time.sleep(0.3)
        
    print("Simülasyon bitti.")