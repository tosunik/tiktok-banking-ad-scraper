# Yeni Repo Oluşturma ve Railway Deployment Rehberi

## 🚀 Adım 1: GitHub'da Yeni Repo Oluştur

1. GitHub'a giriş yap: https://github.com
2. Sağ üstteki **"+"** butonuna tıkla → **"New repository"**
3. Repo bilgilerini gir:
   - **Repository name**: `tiktok-banking-ad-scraper` (veya istediğin isim)
   - **Description**: "TikTok Banking Ad Scraper - N8N Integration"
   - **Visibility**: Public veya Private (tercihine göre)
   - **⚠️ ÖNEMLİ**: "Initialize this repository with a README" seçeneğini **İŞARETLEME**
   - "Add .gitignore" ve "Choose a license" seçeneklerini de **İŞARETLEME**
4. **"Create repository"** butonuna tıkla

## 🔗 Adım 2: Mevcut Repo'yu Yeni Repo'ya Bağla

Terminal'de şu komutları çalıştır:

```bash
cd /Users/oguzhantosun/n8n_TiktokAdScraper/tiktok-ad-scraper

# Mevcut remote'u kaldır
git remote remove origin

# Yeni remote ekle (YOUR_USERNAME ve REPO_NAME'i değiştir)
git remote add origin https://github.com/YOUR_USERNAME/tiktok-banking-ad-scraper.git

# Tüm branch'leri push et
git push -u origin main
```

**Örnek:**
```bash
git remote remove origin
git remote add origin https://github.com/tosunik/tiktok-banking-ad-scraper.git
git push -u origin main
```

## 🚂 Adım 3: Railway'de Yeni Servis Oluştur

1. Railway dashboard'a git: https://railway.app
2. **"New Project"** butonuna tıkla
3. **"Deploy from GitHub repo"** seçeneğini seç
4. Yeni oluşturduğun repo'yu seç
5. Railway otomatik olarak:
   - Repo'yu clone eder
   - `requirements.txt`'den bağımlılıkları yükler
   - `Procfile` veya `railway.json`'a göre deploy eder

## ⚙️ Adım 4: Railway Deploy Ayarları

Railway otomatik olarak şunları algılar:
- **Build Command**: `pip install -r requirements.txt` (otomatik)
- **Start Command**: `python fastapi_server.py` (Procfile'dan)
- **Port**: Railway otomatik set eder

Eğer manuel ayar gerekirse:
1. Railway dashboard → Projen → **Settings**
2. **Deploy** sekmesi:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python fastapi_server.py`

## 🔗 Adım 5: Railway URL'ini Al

1. Railway dashboard → Projen → **Settings**
2. **Networking** sekmesi
3. **Generate Domain** butonuna tıkla
4. URL'i kopyala (örn: `https://tiktok-scraper-production.up.railway.app`)

## 🔄 Adım 6: N8N Workflow'unu Güncelle

1. N8N'de workflow'unu aç
2. **"Run Ad Library Scraper"** node'unu bul
3. URL'i güncelle:
   ```
   Eski: https://n8ntiktokadscraper-production.up.railway.app/scrape-tiktok
   Yeni: https://YENI-RAILWAY-URL.up.railway.app/scrape-tiktok
   ```
4. Workflow'u kaydet ve test et

## ✅ Adım 7: Test Et

### Terminal'den Test:
```bash
curl -X POST https://YENI-RAILWAY-URL.up.railway.app/scrape-tiktok \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["garanti"],
    "max_results": 3,
    "banking_only": true,
    "headless": true
  }'
```

### N8N'den Test:
1. Workflow'u manuel olarak çalıştır
2. "Run Ad Library Scraper" node'unun çıktısını kontrol et
3. Reklamların geldiğini doğrula

## 🐛 Sorun Giderme

### Railway'de Build Hatası:
- `requirements.txt` dosyasının doğru olduğundan emin ol
- Railway logs'u kontrol et: Dashboard → Deployments → Logs

### Port Hatası:
- `fastapi_server.py` dosyasında `PORT` environment variable'ını kullan:
  ```python
  port = int(os.getenv("PORT", 8000))
  ```

### Chrome/Chromium Hatası:
- Railway'de Chrome kurulu olmalı
- `Dockerfile` kullanıyorsan Chrome'u orada kur

## 📝 Notlar

- Railway ücretsiz planında aylık 500 saat limit var
- Her deploy'da yeni bir build oluşturulur
- Environment variables Railway dashboard'dan eklenebilir
- Logs Railway dashboard'dan görüntülenebilir
