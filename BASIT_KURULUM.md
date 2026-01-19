# 🚀 Basit Kurulum Rehberi - Adım Adım

## ADIM 1: GitHub'da Yeni Repo Oluştur (5 dakika)

1. **Tarayıcıda şu adrese git:**
   ```
   https://github.com/new
   ```

2. **Formu doldur:**
   - **Repository name**: `tiktok-banking-ad-scraper` (veya istediğin isim)
   - **Description**: "TikTok Banking Ad Scraper for N8N"
   - **Public** veya **Private** seç (tercihine göre)
   
3. **⚠️ ÖNEMLİ - Şunları İŞARETLEME:**
   - ❌ "Add a README file" 
   - ❌ "Add .gitignore"
   - ❌ "Choose a license"
   
   (Bunları işaretleme çünkü zaten var)

4. **Yeşil "Create repository" butonuna tıkla**

5. **Sayfa açıldığında, şu komutları göreceksin. Şimdilik kapat, biz terminal'den yapacağız.**

---

## ADIM 2: Terminal'de Komutları Çalıştır (2 dakika)

Terminal'i aç (Mac'te Spotlight'a "Terminal" yaz) ve şu komutları sırayla çalıştır:

```bash
# 1. Proje klasörüne git
cd /Users/oguzhantosun/n8n_TiktokAdScraper/tiktok-ad-scraper

# 2. Eski GitHub bağlantısını kaldır
git remote remove origin

# 3. Yeni GitHub repo'yu bağla
# ⚠️ BURADA KENDİ BİLGİLERİNİ YAZ:
# - YOUR_USERNAME: GitHub kullanıcı adın (örn: tosunik)
# - REPO_NAME: Az önce oluşturduğun repo adı (örn: tiktok-banking-ad-scraper)
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# Örnek:
# git remote add origin https://github.com/tosunik/tiktok-banking-ad-scraper.git

# 4. Tüm dosyaları GitHub'a yükle
git push -u origin main
```

**Not:** Eğer GitHub şifresi istenirse, GitHub'da bir "Personal Access Token" oluşturman gerekebilir. Ama genelde sorunsuz çalışır.

---

## ADIM 3: Railway'de Yeni Servis Oluştur (5 dakika)

1. **Railway dashboard'a git:**
   ```
   https://railway.app
   ```

2. **"New Project" butonuna tıkla**

3. **"Deploy from GitHub repo" seçeneğini seç**

4. **Az önce oluşturduğun yeni repo'yu seç**
   - Repo listesinde `tiktok-banking-ad-scraper` (veya verdiğin isim) görünecek
   - Ona tıkla

5. **Railway otomatik olarak:**
   - ✅ Repo'yu indirir
   - ✅ Dockerfile'ı bulur
   - ✅ Bağımlılıkları yükler
   - ✅ Servisi başlatır

6. **Bekle (2-3 dakika sürebilir)**
   - Railway build yapıyor, sabırlı ol

---

## ADIM 4: Railway URL'ini Al (1 dakika)

1. **Railway dashboard'da projenin üstüne tıkla**

2. **Sağ üstte "Settings" butonuna tıkla**

3. **"Networking" sekmesine git**

4. **"Generate Domain" butonuna tıkla**

5. **Oluşan URL'i kopyala**
   - Örnek: `https://tiktok-scraper-production.up.railway.app`
   - Bu URL'i bir yere kaydet

---

## ADIM 5: N8N Workflow'unu Güncelle (2 dakika)

1. **N8N'i aç**

2. **Workflow'unu bul ve aç**

3. **"Run Ad Library Scraper" node'unu bul**

4. **URL kısmını bul ve değiştir:**
   ```
   ESKİ: https://n8ntiktokadscraper-production.up.railway.app/scrape-tiktok
   YENİ: https://YENI-RAILWAY-URL.up.railway.app/scrape-tiktok
   ```
   
   (YENI-RAILWAY-URL yerine ADIM 4'te kopyaladığın URL'i yapıştır)

5. **Workflow'u kaydet (Ctrl+S veya Cmd+S)**

---

## ADIM 6: Test Et (1 dakika)

1. **N8N'de workflow'unu manuel çalıştır**
   - "Execute Workflow" butonuna tıkla

2. **"Run Ad Library Scraper" node'unun çıktısına bak**
   - Yeşil tik görürsen ✅ başarılı
   - Kırmızı X görürsen ❌ hata var, loglara bak

3. **Reklamların geldiğini kontrol et**
   - Switch node'da video/image ayrımı yapılıyor mu?
   - Media URL'leri var mı?

---

## ✅ Tamamlandı!

Artık yeni repo'ndan çalışıyorsun. Eski repo'ya bağımlı değilsin.

---

## 🐛 Sorun mu var?

### "git push" hatası veriyor:
- GitHub kullanıcı adı ve şifreni kontrol et
- Personal Access Token gerekebilir: https://github.com/settings/tokens

### Railway build hatası:
- Railway dashboard → Deployments → Logs'a bak
- Dockerfile doğru mu kontrol et

### N8N'de hata:
- Railway URL'i doğru mu kontrol et
- Railway servisi çalışıyor mu kontrol et (Railway dashboard'da yeşil olmalı)

---

## 📝 Özet Komutlar (Kopyala-Yapıştır İçin)

```bash
cd /Users/oguzhantosun/n8n_TiktokAdScraper/tiktok-ad-scraper
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git
git push -u origin main
```

**YOUR_USERNAME ve REPO_NAME'i değiştirmeyi unutma!**
