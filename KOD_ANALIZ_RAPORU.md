# n8n_tiktok_scraper.py - Detaylı Kod Analizi Raporu

## 📋 Genel Bakış
Bu dosya, N8N otomasyon platformu için TikTok reklam verilerini çeken bir komut satırı aracıdır.

---

## ✅ İŞLEVSEL KODLAR (Çalışan Kısımlar)

### 1. **Import Bölümü (Satır 7-10)**
```7:10:n8n_tiktok_scraper.py
import sys
import json
import argparse
from pathlib import Path
```
**Ne yapar:** Gerekli Python kütüphanelerini yükler.
- `sys`: Sistem işlemleri için
- `json`: JSON veri formatı için
- `argparse`: Komut satırı argümanlarını parse etmek için
- `pathlib.Path`: Dosya yolu işlemleri için

### 2. **Modül Import (Satır 12-15)**
```12:15:n8n_tiktok_scraper.py
# Proje modüllerini import et
sys.path.append(str(Path(__file__).parent))
from src.config.settings import settings
from src.scraper.tiktok_scraper import TikTokAdScraper
```
**Ne yapar:** Proje modüllerini yükler.
- `sys.path.append`: Proje klasörünü Python path'ine ekler
- `TikTokAdScraper`: Ana scraper sınıfını import eder

### 3. **Argüman Parser (Satır 18-24)**
```18:24:n8n_tiktok_scraper.py
parser = argparse.ArgumentParser(description='TikTok Ad Scraper for N8N')
parser.add_argument('--keywords', default='banka,kredi,kart,finans', 
                   help='Comma-separated keywords')
parser.add_argument('--max-results', type=int, default=100,
                   help='Maximum number of ads to scrape')
parser.add_argument('--output-format', choices=['json', 'n8n'], default='n8n',
                   help='Output format')
```
**Ne yapar:** Komut satırından argümanları alır.
- `--keywords`: Aranacak anahtar kelimeler (varsayılan: "banka,kredi,kart,finans")
- `--max-results`: Maksimum reklam sayısı (varsayılan: 100)
- `--output-format`: Çıktı formatı (json veya n8n, varsayılan: n8n)

### 4. **Scraper Çalıştırma (Satır 29-33)**
```29:33:n8n_tiktok_scraper.py
# Scraper'ı çalıştır
scraper = TikTokAdScraper(headless=True)  # N8N'de headless
keywords = args.keywords.split(',')
result = scraper.search_ads(keywords, args.max_results)
```
**Ne yapar:** 
- Scraper nesnesi oluşturur (headless modda - tarayıcı penceresi açılmaz)
- Anahtar kelimeleri virgülle ayırarak liste yapar
- Scraping işlemini başlatır ve sonuçları `result` değişkenine kaydeder

### 5. **N8N Formatında Çıktı (Satır 36-55)**
```36:55:n8n_tiktok_scraper.py
if args.output_format == 'n8n':
    # N8N'nin beklediği format: array of objects
    n8n_output = []
    
    for ad in scraper.scraped_ads:
        ad_dict = ad.dict()
        
        # N8N için ek meta bilgiler
        ad_dict['n8n_meta'] = {
            'media_count': len(ad_dict.get('media_urls', [])),
            'has_video': ad.is_video(),
            'has_image': ad.is_image(),
            'is_banking': ad.is_banking_ad,
            'processing_priority': 'high' if ad.is_banking_ad else 'normal'
        }
        
        n8n_output.append(ad_dict)
    
    # N8N output
    print(json.dumps(n8n_output, ensure_ascii=False, default=str))
```
**Ne yapar:** 
- N8N formatında çıktı hazırlar
- Her reklam için ek meta bilgiler ekler (medya sayısı, video/resim kontrolü, bankacılık reklamı mı, öncelik seviyesi)
- JSON formatında yazdırır

### 6. **JSON Formatında Çıktı (Satır 57-69)**
```57:69:n8n_tiktok_scraper.py
else:
    # Standard JSON format
    output = {
        'summary': {
            'total_ads': result.total_ads,
            'banking_ads': result.banking_ads,
            'video_ads': result.video_ads,
            'image_ads': result.image_ads,
            'duration_seconds': result.duration_seconds
        },
        'ads': [ad.dict() for ad in scraper.scraped_ads]
    }
    print(json.dumps(output, ensure_ascii=False, default=str))
```
**Ne yapar:**
- Standart JSON formatında çıktı hazırlar
- Özet bilgileri içerir (toplam reklam, bankacılık reklamları, video/resim reklamları, süre)
- Tüm reklamları listeler

### 7. **Hata Yönetimi (Satır 71-79)**
```71:79:n8n_tiktok_scraper.py
except Exception as e:
    # N8N error format
    error_output = {
        'error': True,
        'message': str(e),
        'type': type(e).__name__
    }
    print(json.dumps(error_output))
    sys.exit(1)
```
**Ne yapar:**
- Hata durumunda N8N uyumlu hata mesajı döndürür
- Hata tipini ve mesajını içerir
- Programı hata kodu ile sonlandırır

### 8. **Main Çağrısı (Satır 81-82)**
```81:82:n8n_tiktok_scraper.py
if __name__ == "__main__":
    main()
```
**Ne yapar:** Script doğrudan çalıştırıldığında `main()` fonksiyonunu çağırır.

---

## ❌ İŞLEVSİZ KODLAR (Kullanılmayan Kısımlar)

### 1. **Kullanılmayan Import: `settings` (Satır 14)**
```14:14:n8n_tiktok_scraper.py
from src.config.settings import settings
```

**Sorun:** 
- `settings` modülü import ediliyor ama kodun hiçbir yerinde kullanılmıyor
- Bu gereksiz bir import ve kod karmaşıklığını artırıyor

**Çözüm:** Bu satırı kaldırabilirsiniz:
```python
# Bu satırı silin:
from src.config.settings import settings
```

**Neden kullanılmıyor?**
- Kod içinde `settings` değişkenine hiçbir referans yok
- `TikTokAdScraper` sınıfı kendi içinde `settings`'i kullanıyor olabilir, ama bu dosyada gerekli değil

---

## 📊 ÖZET

### İşlevsel Kodlar:
- ✅ Tüm import'lar (settings hariç)
- ✅ Argüman parser
- ✅ Scraper çalıştırma
- ✅ N8N formatında çıktı
- ✅ JSON formatında çıktı
- ✅ Hata yönetimi
- ✅ Main fonksiyonu

### İşlevsiz Kodlar:
- ❌ Satır 14: `from src.config.settings import settings` - Hiç kullanılmıyor

---

## 🔧 ÖNERİLER

1. **Kullanılmayan import'u kaldırın:**
   - Satır 14'teki `settings` import'unu silin

2. **Kod temizliği:**
   - Gereksiz import'lar performansı etkilemese de kod okunabilirliğini azaltır

3. **Test:**
   - Kodun çalışıp çalışmadığını test etmek için:
   ```bash
   python3 n8n_tiktok_scraper.py --keywords "test" --max-results 5 --output-format json
   ```

