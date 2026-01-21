# TikTok Banking Ad Scraper

Türk bankacılık sektörüne odaklı TikTok reklam toplama ve analiz aracı. N8N workflow'ları ile entegre çalışır ve Railway üzerinde deploy edilebilir.

## 🚀 Özellikler

- **TikTok Ad Library Scraping**: Selenium ile TikTok reklam kütüphanesinden reklam toplama
- **Bankacılık Filtreleme**: Türk bankalarına özel anahtar kelime filtreleme
- **Medya Türü Desteği**: Video, resim ve metin reklamlarını destekler
- **N8N Entegrasyonu**: FastAPI ile N8N workflow'larına entegre edilebilir
- **Railway Deploy**: Railway üzerinde kolayca deploy edilebilir
- **Hızlı Test Modu**: Geliştirme için optimize edilmiş hızlı test modu
- **Gerçek Media URL'leri**: TikTok CDN'den gerçek video/image URL'leri

## 📋 Gereksinimler

- Python 3.8+
- Chrome/Chromium tarayıcı
- İnternet bağlantısı

## 🛠️ Kurulum

1. **Repository'yi klonlayın:**
```bash
git clone https://github.com/YOUR_USERNAME/tiktok-banking-ad-scraper.git
cd tiktok-banking-ad-scraper
```

2. **Sanal ortam oluşturun:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate     # Windows
```

3. **Gerekli paketleri yükleyin:**
```bash
pip install -r requirements.txt
```

## 🎯 Kullanım

### Komut Satırı (N8N için)

```bash
python n8n_tiktok_scraper.py --keywords "garanti,isbank" --max-results 50 --output-format n8n
```

### FastAPI Server (N8N için)

```bash
python fastapi_server.py
```

Server `http://localhost:8000` adresinde çalışacaktır.

### API Endpoints

- `GET /` - API bilgileri
- `GET /health` - Sağlık kontrolü
- `POST /scrape-tiktok` - Reklam toplama işlemi (N8N için)
- `GET /test-scrape` - Hızlı test endpoint'i
- `GET /turkish-banks` - Türk bankaları listesi

### N8N Integration

N8N workflow'unuzda şu şekilde kullanın:

```json
{
  "method": "POST",
  "url": "https://your-railway-app.up.railway.app/scrape-tiktok",
  "body": {
    "keywords": ["garanti", "isbank"],
    "max_results": 50,
    "banking_only": true,
    "headless": true
  }
}
```

Response formatı (N8N için):
```json
[
  {
    "ad_id": "...",
    "advertiser_name": "TURKIYE GARANTI BANKASI ANONIM SIRKETI",
    "ad_text": "...",
    "media_type": "video",
    "media_urls": ["https://p21-ad-sg.ibyteimg.com/..."],
    "is_banking_ad": true,
    "scraped_at": "2026-01-19T14:18:35",
    "n8n_meta": {
      "media_count": 1,
      "has_video": true,
      "has_image": false,
      "is_banking": true,
      "processing_priority": "high"
    }
  }
]
```

## 📁 Proje Yapısı

```
tiktok-ad-scraper/
├── src/
│   ├── config/          # Yapılandırma dosyaları
│   │   └── settings.py
│   ├── models/          # Veri modelleri
│   │   └── ad_model.py
│   ├── scraper/         # Scraping mantığı
│   │   ├── tiktok_scraper.py
│   │   └── tiktok_selenium_scraper.py
│   └── utils/           # Yardımcı fonksiyonlar
│       ├── helpers.py
│       └── proxy_manager.py
├── data/               # Toplanan veriler (gitignore'da)
├── logs/               # Log dosyaları (gitignore'da)
├── n8n_tiktok_scraper.py  # N8N CLI wrapper
├── fastapi_server.py   # N8N FastAPI server
├── requirements.txt    # Python bağımlılıkları
├── Procfile           # Railway deployment
└── railway.json       # Railway config
```

## ⚙️ Yapılandırma

Uygulama ayarları `src/config/settings.py` dosyasında bulunur:

- `tiktok_max_ads_per_search`: Arama başına maksimum reklam sayısı (default: 200)
- `log_level`: Log seviyesi (default: INFO)
- `banking_keywords`: Bankacılık anahtar kelimeleri

## 🚂 Railway Deployment

1. **Railway'de yeni proje oluşturun**
2. **GitHub repo'yu bağlayın**
3. **Deploy settings:**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python fastapi_server.py`
   - Port: Railway otomatik set eder

4. **Environment Variables (opsiyonel):**
   - `PORT=8000`
   - `LOG_LEVEL=INFO`

## 📊 Çıktı Formatı

### N8N Format (Array of Objects)
```json
[
  {
    "ad_id": "selenium_0_1234567890",
    "advertiser_name": "TURKIYE GARANTI BANKASI ANONIM SIRKETI",
    "media_type": "video",
    "media_urls": ["https://..."],
    "is_banking_ad": true,
    "n8n_meta": {...}
  }
]
```

### Standard JSON Format
```json
{
  "summary": {
  "total_ads": 50,
  "banking_ads": 12,
  "video_ads": 30,
  "image_ads": 15,
    "duration_seconds": 45.2
  },
  "ads": [...]
}
```

## 🔧 Geliştirme

### Test Çalıştırma

```bash
# Hızlı test (3 reklam)
python n8n_tiktok_scraper.py --keywords "isbank" --max-results 3 --output-format json

# FastAPI test
python fastapi_server.py
# Başka terminal: curl http://localhost:8000/test-scrape
```

### Kod Formatlama

```bash
black .
flake8 .
```

## 🆕 Son Güncellemeler

- ✅ TikTok'un yeni URL yapısına uyum sağlandı
- ✅ Test süresi optimize edildi (~30s → ~24s)
- ✅ Gerçek TikTok CDN URL'leri çıkarılıyor
- ✅ Advertiser name temizleme iyileştirildi
- ✅ N8N uyumlu response formatı

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## ⚠️ Uyarılar

- Bu araç sadece eğitim ve araştırma amaçlıdır
- TikTok'un kullanım şartlarına uygun şekilde kullanın
- Rate limiting ve etik scraping kurallarına uyun
- Kişisel verileri koruma yasalarına dikkat edin

## 📞 İletişim

Sorularınız için issue açabilir veya iletişime geçebilirsiniz.
