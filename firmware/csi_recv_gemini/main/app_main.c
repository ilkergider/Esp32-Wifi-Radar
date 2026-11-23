#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"

#define WIFI_CHANNEL 6  // Dinlenecek Wi-Fi kanalı

static const char *TAG = "CSI_RECV";

// CSI verisi havadan yakalandığında otomatik tetiklenen fonksiyon (Callback)
static void wifi_csi_rx_cb(void *ctx, wifi_csi_info_t *info)
{
    if (!info || !info->buf) {
        return;
    }

    wifi_csi_info_t *csi_info = info;
    int8_t *my_csi_raw = csi_info->buf;

    // Python tarafının kolayca ayrıştırması için özel etiketli çıktı:
    // Format: CSI_DATA, <RSSI_DEGERI>, <VERI_UZUNLUGU>, [I1, Q1, I2, Q2, ...]
    printf("CSI_DATA,%d,%d,", csi_info->rx_ctrl.rssi, csi_info->len);
    for (int i = 0; i < csi_info->len; i++) {
        printf("%d%s", my_csi_raw[i], (i == csi_info->len - 1) ? "" : ",");
    }
    printf("\n");
}

// Wi-Fi ve CSI Başlatma Ayarları
static void wifi_csi_init(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());
    
    // Wi-Fi Kanalı Ayarlama
    ESP_ERROR_CHECK(esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE));

    // CSI Ayarları
    wifi_csi_config_t csi_config = {
        .lltf_en           = true,
        .htltf_en          = true,
        .stbc_htltf2_en    = true,
        .ltf_merge_en      = true,
        .channel_filter_en = true,
        .manu_scale        = false,
        .shift             = false,
    };

    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(wifi_csi_rx_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));

    ESP_LOGI(TAG, "Wi-Fi CSI Dinleme Başlatıldı. Kanal: %d", WIFI_CHANNEL);
}

void app_main(void)
{
    // NVS (Non-Volatile Storage) Başlatma
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ESP_LOGI(TAG, "ESP32 CSI Alıcı Sistem Başlatılıyor...");
    wifi_csi_init();
}