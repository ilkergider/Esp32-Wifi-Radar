import numpy as np
from scipy.signal import butter, filtfilt

def parse_csi_raw(raw_data_list):
    """
    ESP32'den gelen ham karmaşık sayı dizisini 
    Genlik (Amplitude) değerlerine çevirir.
    """
    raw_array = np.array(raw_data_list, dtype=float)
    real = raw_array[0::2]
    imag = raw_array[1::2]
    amplitudes = np.sqrt(real**2 + imag**2)
    return amplitudes

def butter_lowpass_filter(data, cutoff=2.0, fs=20.0, order=4):
    """
    Sinyaldeki yüksek frekanslı gürültüyü temizler.
    """
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    filtered_data = filtfilt(b, a, axis=0)
    return filtered_data