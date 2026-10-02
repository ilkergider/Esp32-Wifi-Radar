# ESP32 Wi-Fi CSI Tabanlı İç Mekan Varlık ve Hareket Tespiti

Bu proje, ortama kamera veya ek giyilebilir sensör eklemeden, Wi-Fi sinyallerindeki **CSI (Channel State Information)** verilerini kullanarak iç mekanda varlık, hareket ve bölge tespiti gerçekleştirmeyi hedefleyen bir lisans tezi çalışmasıdır.

Proje Amaçları
- ESP32 kartları kullanarak ortamdaki Wi-Fi CSI verilerini toplamak.
- Dijital sinyal işleme (DSP) teknikleri ile ham verideki gürültüyü temizlemek.
- Makine öğrenmesi modelleri ile alan/bölge bazlı insan varlığı tespiti yapmak.
- Elde edilen verileri anlık olarak bir 2D ısı haritası (Heatmap) üzerinde görselleştirmek.

Kullanılan Teknolojiler
- **Gömülü Sistemler:** ESP32, ESP-IDF
- **Veri İşleme & Yapay Zeka:** Python (NumPy, SciPy, Pandas, Scikit-Learn)
- **Görselleştirme:** Matplotlib / OpenCV

Uygulama Alanları
1. Akıllı Bina ve Enerji Yönetimi
2. Gizlilik Odaklı Güvenlik ve Varlık Tespiti
