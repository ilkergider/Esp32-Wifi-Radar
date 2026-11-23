# ESP32 Wi-Fi CSI Tabanlı İç Mekan Varlık ve Hareket Tespiti

Bu proje, ortama kamera veya giyilebilir sensör eklemeden, Wi-Fi sinyallerindeki **CSI (Channel State Information)** verilerini kullanarak iç mekanda varlık, hareket ve bölge tespiti yapmayı hedefleyen bir lisans tezi çalışmasıdır.

## Proje Amaçları
- İki ESP32 kartı (verici + alıcı) ile ortamdaki Wi-Fi CSI verisini toplamak.
- Dijital sinyal işleme (DSP) ile ham verideki gürültüyü temizlemek.
- Makine öğrenmesi ile bölge bazlı insan varlığı tespiti yapmak (ileride kişi sayımı).
- Sonuçları 2D ısı haritası üzerinde görselleştirmek.

## Donanım ve Kurulum
- 2 adet ESP32 (biri `csi_send` verici, biri `csi_recv` alıcı), ESP-IDF v6.1
- Oda yaklaşık 8 × 8 m; kartlar odanın sağına ve soluna, aralarında görüş hattı olacak şekilde yerleştirildi
- **sagsol_v1:** ~5 m mesafe, antenli uçlar karşılıklı → RSSI ≈ -80 dBm (zayıf, paket kaybı yüksek)
- **sagsol_v2:** ~4.2 m mesafe, kartlar ters çevrildi (micro USB uçları karşılıklı) → RSSI ≈ -62 dBm, 61–70 paket/sn

## Klasör Yapısı
```
firmware/
  csi_send/          Verici (Espressif resmi örneği, IDF v6.1 uyarlaması)
  csi_recv/          Alıcı, CSI_DATA satırlarını seri porta basar (gain control kapalı)
  csi_recv_gemini/   İlk deneme sürümü
src/
  serial_logger.py          Seri porttan kayıt: --kisi --konum --durum --yerlesim
  rssi_monitor.py           Canlı RSSI izleme (kart yerleşimi ayarlamak için)
  analyze_csi.py            Kalite raporu, ısı haritaları, fark haritası, hareket skoru
  siniflandir_denemesi.py   Random Forest / SVM ile 5 sınıflı senaryo sınıflandırma
  metrik_karsilastir.py     Hareket metriklerinin karşılaştırması
data/
  metadata.csv              Her kaydın oturum/kişi/konum/durum bilgisi
  analysis/<oturum>/        Analiz çıktıları (PNG, kalite raporu)
  raw/                      Ham kayıtlar (repoda yok, büyük dosyalar)
```

## Veri Toplama Protokolü
Her oturumda 5 senaryo × 3 tekrar × 60 sn = 15 kayıt:
`boş oda`, `sol duran`, `orta duran`, `sağ duran`, `gezen (hareket)`

```
python src\serial_logger.py COM8 --kisi 1 --konum sol --durum duran --yerlesim sagsol_v2
python src\analyze_csi.py --yerlesim sagsol_v2
python src\siniflandir_denemesi.py --yerlesim sagsol_v2
```

## Ön İşleme (analyze_csi.py)
1. Her CSI paketinden I/Q çiftleri okunur, genlik = √(I² + Q²)
2. Her kaydın ilk 5 sn'si (kişi yerine geçerken) ve son 1 sn'si atılır
3. Paket normalizasyonu: her paket kendi ortalama genliğine bölünür (AGC kaynaklı dalgalanmayı giderir)
4. Sıfır/zayıf ve kararsız alt taşıyıcılar (blok sınırları) otomatik ayıklanır
5. Fark haritası: her kayıt boş oda ortalama profiline göre yüzde fark olarak çizilir

## Güncel Sonuçlar (sagsol_v2)
- Gezen kişi ısı haritasında periyodik dikey bantlar (~6–7 sn arayla görüş hattı kesilmesi) olarak açıkça görülüyor.
- Basit eşik tabanlı hareket skorları boş/dolu ayrımını güvenilir yapamadı.
- Random Forest (genlik profili + değişim öznitelikleri, 100 paketlik pencere, bir tekrarı dışarıda bırakarak doğrulama): 5 sınıfta **~%77 dengeli doğruluk**. Sol/orta/sağ iyi ayrılıyor; boş oda ile gezen/sağ duran karışıyor.

## Sıradaki Adımlar
- Farklı günlerde ve karışık senaryo sırasıyla yeni oturum (oturumlar arası genelleme testi)
- Fark haritası tabanlı özniteliklerle duran kişi tespitinin iyileştirilmesi
- Kişi sayımı denemesi (0 / 1 / 2 kişi)
- Canlı tahmin ve ısı haritası arayüzü

## Uygulama Alanları
1. Akıllı bina ve enerji yönetimi
2. Gizlilik odaklı güvenlik ve varlık tespiti

## Referans
Geng, J., Huang, D., De la Torre, F. *DensePose From WiFi*, arXiv:2301.00250
