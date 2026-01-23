# tiktok_selenium_scraper.py dosyanızın başındaki import'ları bu şekilde güncelleyin:

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
# Bu satırı KALDIR - artık gerekli değil: from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import json
import re
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from loguru import logger

from src.config.settings import settings
from src.utils.helpers import safe_sleep, clean_text
def check_url_content_type(url: str, timeout: int = 5) -> str:
    """
    URL'nin Content-Type'ını HEAD request ile kontrol et
    Returns: 'video', 'image', or 'unknown'
    """
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '').lower()
        
        if 'video' in content_type:
            logger.info(f"✅ Content-Type kontrolü: VIDEO ({content_type})")
            return 'video'
        elif 'image' in content_type:
            logger.info(f"⚠️ Content-Type kontrolü: IMAGE ({content_type})")
            return 'image'
        else:
            logger.debug(f"❓ Content-Type belirsiz: {content_type}")
            return 'unknown'
    except Exception as e:
        logger.debug(f"Content-Type kontrolü başarısız: {e}")
        return 'unknown'


class NetworkVideoExtractor:
    """Network requests'lerden video URL'lerini yakalama"""
    
    def __init__(self, driver):
        self.driver = driver
        self.captured_video_urls = []
        self.network_logs = []
    
    def start_network_monitoring(self):
        """Network monitoring başlat"""
        try:
            # Mevcut network logs'u temizle
            self.driver.get_log('performance')
            logger.info("Network monitoring başlatıldı")
        except Exception as e:
            logger.warning(f"Network monitoring başlatılamadı: {e}")
    
    def capture_network_requests(self, duration_seconds: int = 10) -> List[str]:
        """Network isteklerini yakala ve video URL'lerini filtrele"""
        video_urls = []
        
        try:
            # Belirli süre boyunca network isteklerini topla
            start_time = time.time()
            
            while time.time() - start_time < duration_seconds:
                logs = self.driver.get_log('performance')
                
                for log in logs:
                    try:
                        message = json.loads(log['message'])
                        self._process_network_message(message, video_urls)
                    except (json.JSONDecodeError, KeyError):
                        continue
                
                time.sleep(0.5)  # CPU kullanımını azalt
            
            # Duplicate'leri kaldır
            unique_video_urls = list(set(video_urls))
            logger.info(f"Network'den {len(unique_video_urls)} video URL yakalandı")
            
            return unique_video_urls
            
        except Exception as e:
            logger.error(f"Network capture hatası: {e}")
            return []
    
    def _process_network_message(self, message: dict, video_urls: List[str]):
        """Network message'ını işle ve video URL'lerini çıkar"""
        try:
            msg_method = message.get('message', {}).get('method', '')
            
            # Response received events
            if msg_method == 'Network.responseReceived':
                response = message['message']['params']['response']
                url = response.get('url', '')
                mime_type = response.get('mimeType', '')
                
                # Video URL kontrolü
                if self._is_video_url(url, mime_type):
                    video_urls.append(url)
                    logger.debug(f"Video URL yakalandı: {url[:100]}...")
            
            # Request sent events (bazı durumlarda yararlı)
            elif msg_method == 'Network.requestWillBeSent':
                request = message['message']['params']['request']
                url = request.get('url', '')
                
                if self._is_video_url(url):
                    video_urls.append(url)
                    logger.debug(f"Video request yakalandı: {url[:100]}...")
                    
        except Exception as e:
            logger.debug(f"Network message processing error: {e}")
    
    def _is_video_url(self, url: str, mime_type: str = '') -> bool:
        """URL'nin video olup olmadığını kontrol et"""
        if not url or not isinstance(url, str):
            return False
        
        # URL pattern kontrolü
        video_patterns = [
            r'\.mp4',
            r'\.mov',
            r'\.avi',
            r'\.webm',
            r'\.m4v',
            r'/video/',
            r'video\.tiktok',
            r'\.tiktokcdn\.',
            r'\.ttwstatic\.',
            r'\.tiktokv\.',
            r'\.musical\.ly'
        ]
        
        # MIME type kontrolü
        if mime_type:
            if 'video' in mime_type.lower():
                return True
        
        # URL pattern kontrolü
        for pattern in video_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                # Thumbnail/poster image'ları exclude et
                if not re.search(r'(thumb|poster|preview|cover)(?!nail)', url, re.IGNORECASE):
                    return True
        
        return False
    
    def extract_video_from_detail_page(self, ad_element, max_wait: int = 15) -> Optional[str]:
        """Reklam detay sayfasına gidip video URL çıkar"""
        original_window = self.driver.current_window_handle
        
        try:
            # Detay linkini bul
            link_elem = ad_element.find_element(By.CSS_SELECTOR, 'a[href*="detail"]')
            detail_url = link_elem.get_attribute('href')
            
            if not detail_url:
                return None
            
            logger.info(f"Detay sayfasına gidiliyor: {detail_url[:100]}...")
            
            # Yeni tab'da aç
            self.driver.execute_script("window.open(arguments[0], '_blank');", detail_url)
            
            # Yeni tab'a geç
            detail_window = None
            for window in self.driver.window_handles:
                if window != original_window:
                    detail_window = window
                    break
            
            if not detail_window:
                return None
            
            self.driver.switch_to.window(detail_window)
            
            # Network monitoring başlat
            self.start_network_monitoring()
            
            # Sayfa yüklensin ve video player hazır olsun
            time.sleep(3)
            
            # Video element'ini trigger et (play button vs.)
            self._trigger_video_load()
            
            # Network isteklerini yakala
            video_urls = self.capture_network_requests(duration_seconds=max_wait)
            
            # Tab'ı kapat
            self.driver.close()
            self.driver.switch_to.window(original_window)
            
            # En iyi video URL'i seç
            if video_urls:
                best_url = self._select_best_video_url(video_urls)
                logger.info(f"Detay sayfasından video URL bulundu: {best_url[:100]}...")
                return best_url
            
            return None
            
        except Exception as e:
            logger.error(f"Detay sayfası video extraction hatası: {e}")
            
            # Cleanup: Tab'ı kapat
            try:
                if detail_window and detail_window in self.driver.window_handles:
                    self.driver.switch_to.window(detail_window)
                    self.driver.close()
                self.driver.switch_to.window(original_window)
            except:
                pass
            
            return None
    
    def _trigger_video_load(self):
        """Video yüklemeyi tetikle"""
        try:
            # Video elementlerini bul ve play'e bas
            video_triggers = [
                'video',
                '.video-player',
                '.video_player',
                '[data-testid*="video"]',
                '.play-button',
                '[aria-label*="play"]'
            ]
            
            for selector in video_triggers:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        # Click veya hover ile video yüklemeyi tetikle
                        self.driver.execute_script("arguments[0].click();", elem)
                        time.sleep(1)
                        
                        # Video varsa play et
                        if elem.tag_name == 'video':
                            self.driver.execute_script("arguments[0].play();", elem)
                            time.sleep(2)
                            self.driver.execute_script("arguments[0].pause();", elem)
                        
                except Exception:
                    continue
                    
        except Exception as e:
            logger.debug(f"Video trigger hatası: {e}")
    
    def _select_best_video_url(self, video_urls: List[str]) -> str:
        """En iyi video URL'i seç"""
        if not video_urls:
            return None
        
        # Priority order
        priorities = [
            (r'\.mp4', 10),           # MP4 format priority
            (r'\.webm', 8),           # WebM format
            (r'\.mov', 6),            # MOV format
            (r'/video/', 5),          # Video path'li URL'ler
            (r'\.tiktokcdn\.', 8),    # TikTok CDN
            (r'\.ttwstatic\.', 7),    # TikTok static
            (r'high|hd|720|1080', 9), # Yüksek kalite işaretleri
        ]
        
        scored_urls = []
        
        for url in video_urls:
            score = 0
            for pattern, points in priorities:
                if re.search(pattern, url, re.IGNORECASE):
                    score += points
            
            # Daha uzun URL'ler genelde daha detaylı (parameter'lar vs.)
            score += min(len(url) // 100, 3)
            
            scored_urls.append((score, url))
        
        # En yüksek skorlu URL'i döndür
        scored_urls.sort(reverse=True, key=lambda x: x[0])
        
        logger.debug(f"URL skorları: {[(score, url[:50]) for score, url in scored_urls[:3]]}")
        
        return scored_urls[0][1] if scored_urls else video_urls[0]

class TikTokSeleniumScraper:
    """Selenium ile TikTok Ad Library Scraper"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.base_url = "https://library.tiktok.com"
        self.scraped_ads = []
        
    def setup_driver(self):
        """Chrome WebDriver kurulumu - Modern Selenium ile Network Logging"""
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # Temel Chrome argumentları
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Network logging için kritik argumentlar
            chrome_options.add_argument("--enable-logging")
            chrome_options.add_argument("--log-level=0")
            chrome_options.add_argument("--enable-network-service-logging")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            
            # Modern Selenium için logging preferences
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('prefs', {
                'profile.default_content_setting_values.notifications': 2,
                'profile.default_content_settings.popups': 0,
            })
            
            # Performance logging için modern approach
            chrome_options.set_capability('goog:loggingPrefs', {
                'performance': 'ALL',
                'browser': 'ALL'
            })
            
            # WebDriver oluştur - Modern syntax
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(
                service=service, 
                options=chrome_options
            )
            
            # Chrome DevTools Protocol komutlarını aktifleştir
            self.driver.execute_cdp_cmd('Network.enable', {})
            self.driver.execute_cdp_cmd('Performance.enable', {})
            self.driver.execute_cdp_cmd('Runtime.enable', {})
            
            # Network events'leri dinlemeye başla
            self.driver.execute_cdp_cmd('Network.setCacheDisabled', {'cacheDisabled': True})
            
            logger.info("Chrome WebDriver hazırlandı (Network logging AKTIF)")
            return True
            
        except Exception as e:
            logger.error(f"WebDriver kurulum hatası: {e}")
            return False
    def close_driver(self):
        """WebDriver'ı kapat"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver kapatıldı")
    
    def build_search_url(self, 
                        advertiser_name: str = "",
                        keyword: str = "",
                        region: str = "TR",
                        days_back: int = 30) -> str:
        """TikTok Ad Library arama URL'i oluştur
        
        Args:
            advertiser_name: Reklam veren adı (tam eşleşme arar)
            keyword: Genel keyword (reklam içeriğinde arar) - advertiser_name yerine kullanılabilir
            region: Ülke kodu
            days_back: Kaç gün geriye gidilecek
        """
        
        # Tarih aralığı hesapla (Unix timestamp milisaniye)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        
        start_timestamp = int(start_time.timestamp() * 1000)
        end_timestamp = int(end_time.timestamp() * 1000)
        
        url = f"{self.base_url}/ads"
        
        # Keyword veya advertiser name (ikisi aynı parametreyi kullanıyor)
        search_term = keyword if keyword else advertiser_name
        
        params = [
            f"region={region}",
            f"start_time={start_timestamp}",
            f"end_time={end_timestamp}",
            f"adv_name={search_term}" if search_term else "adv_name=",
            "adv_biz_ids=",  # TikTok'un güncel URL formatında gerekli (boş string)
            "query_type=1",
            "sort_type=last_shown_date,desc"
        ]
        
        return url + "?" + "&".join(params)
    
    def search_ads_by_advertiser(self, advertiser_names: List[str], max_ads: int = 100) -> List[Dict]:
        """Reklam veren adlarına göre reklam ara"""
        all_ads = []
        
        if not self.setup_driver():
            logger.error("WebDriver kurulamadı")
            return []
        
        try:
            # Eğer sadece bir advertiser aranıyorsa, tüm max_ads'i ondan al
            # Birden fazla advertiser varsa, her birinden eşit dağıt
            if len(advertiser_names) == 1:
                # Tek advertiser için tüm max_ads'i kullan
                max_ads_per_search = max_ads
            else:
                # Birden fazla advertiser için eşit dağıt (minimum 3, maksimum max_ads / advertiser sayısı)
                max_ads_per_search = max(3, max_ads // len(advertiser_names))
            
            logger.info(f"Her advertiser için maksimum {max_ads_per_search} reklam aranacak")
            
            for advertiser in advertiser_names:
                logger.info(f"'{advertiser}' reklamları aranıyor...")
                
                search_url = self.build_search_url(advertiser_name=advertiser)
                logger.info(f"URL: {search_url}")
                
                # Kalan reklam sayısını hesapla
                remaining_ads = max_ads - len(all_ads)
                current_max = min(max_ads_per_search, remaining_ads)
                
                ads = self._scrape_ads_from_url(search_url, max_ads_per_search=current_max)
                all_ads.extend(ads)
                
                logger.info(f"'{advertiser}' için {len(ads)} reklam bulundu (Toplam: {len(all_ads)})")
                
                # Rate limiting
                safe_sleep(3, 5)
                
                if len(all_ads) >= max_ads:
                    break
            
            logger.info(f"Toplam {len(all_ads)} reklam scrape edildi")
            
        except Exception as e:
            logger.error(f"Selenium scraping hatası: {e}")
        
        finally:
            self.close_driver()
        
        return all_ads
    
    def search_ads_by_keyword(self, keywords: List[str], max_ads: int = 100) -> List[Dict]:
        """Keyword'lere göre reklam ara (advertiser name değil, genel arama)
        
        Args:
            keywords: Aranacak keyword'ler (örn: ["banka", "kredi"])
            max_ads: Maksimum reklam sayısı
            
        Returns:
            Bulunan reklamların listesi
        """
        all_ads = []
        
        if not self.setup_driver():
            logger.error("WebDriver kurulamadı")
            return []
        
        try:
            # Her keyword için maksimum reklam sayısı
            if len(keywords) == 1:
                max_ads_per_search = max_ads
            else:
                max_ads_per_search = max(3, max_ads // len(keywords))
            
            logger.info(f"Her keyword için maksimum {max_ads_per_search} reklam aranacak")
            
            for kw in keywords:
                logger.info(f"'{kw}' keyword'ü aranıyor...")
                
                search_url = self.build_search_url(keyword=kw)
                logger.info(f"URL: {search_url}")
                
                # Kalan reklam sayısını hesapla
                remaining_ads = max_ads - len(all_ads)
                current_max = min(max_ads_per_search, remaining_ads)
                
                ads = self._scrape_ads_from_url(search_url, max_ads_per_search=current_max)
                all_ads.extend(ads)
                
                logger.info(f"'{kw}' için {len(ads)} reklam bulundu (Toplam: {len(all_ads)})")
                
                # Rate limiting
                safe_sleep(3, 5)
                
                if len(all_ads) >= max_ads:
                    break
            
            logger.info(f"Toplam {len(all_ads)} reklam scrape edildi")
            
        except Exception as e:
            logger.error(f"Selenium scraping hatası: {e}")
        
        finally:
            self.close_driver()
        
        return all_ads
    
    def search_banking_ads(self, max_ads: int = 100) -> List[Dict]:
        """Türk bankalarının reklamlarını ara (keyword-based)"""
        
        # Bankacılık keyword'leri (advertiser name yerine)
        banking_keywords = ["banka", "kredi", "hesap", "kart"]
        
        return self.search_ads_by_keyword(banking_keywords, max_ads)
    
    def _scrape_ads_from_url(self, url: str, max_ads_per_search: int = 3) -> List[Dict]:
        """Belirli URL'den reklamları scrape et - Hızlı test versiyonu"""
        ads = []
        
        try:
            self.driver.get(url)
            
            # Sayfanın yüklenmesini bekle
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            logger.info("Sayfa yüklendi, Search butonunu arıyorum...")
            time.sleep(3)
            
            # #region agent log
            # DEBUG: Sayfadaki tüm butonları logla
            try:
                import json
                debug_log_path = '/app/debug.log'
                current_url = self.driver.current_url
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                button_texts = [btn.text for btn in all_buttons[:10]]  # İlk 10 buton
                
                # Total ads değerini bul
                total_ads_text = "not_found"
                try:
                    total_elem = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Total ads')]")
                    total_ads_text = total_elem.text
                except:
                    pass
                
                with open(debug_log_path, 'a') as f:
                    f.write(json.dumps({
                        "timestamp": int(time.time() * 1000),
                        "location": "tiktok_selenium_scraper.py:510",
                        "message": "Pre-search button state",
                        "data": {
                            "url": current_url,
                            "buttons_found": len(all_buttons),
                            "button_texts": button_texts,
                            "total_ads_text": total_ads_text
                        },
                        "sessionId": "debug-session",
                        "hypothesisId": "A"
                    }) + '\n')
            except Exception as log_e:
                logger.debug(f"Debug log failed: {log_e}")
            # #endregion
            
            # ZORUNLU: Search butonuna tıkla (URL parametresi çalışmıyor!)
            # Advertiser name zaten input'ta (URL'den geldi), sadece Search'e tıkla
            try:
                # Search butonunu bul ve tıkla
                search_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Search') or contains(text(), 'search')]"))
                )
                logger.info("Search butonuna tıklıyorum...")
                search_button.click()
                
                # Sonuçların yüklenmesini UZUN BEKLE
                logger.info("Filtrelenmiş sonuçlar yükleniyor...")
                time.sleep(8)
                
                # #region agent log
                # DEBUG: Search'ten sonra durum
                try:
                    import json
                    debug_log_path = '/app/debug.log'
                    post_url = self.driver.current_url
                    post_total_ads = "not_found"
                    try:
                        total_elem = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Total ads')]")
                        post_total_ads = total_elem.text
                    except:
                        pass
                    
                    with open(debug_log_path, 'a') as f:
                        f.write(json.dumps({
                            "timestamp": int(time.time() * 1000),
                            "location": "tiktok_selenium_scraper.py:540",
                            "message": "Post-search button state",
                            "data": {
                                "url": post_url,
                                "total_ads_text": post_total_ads,
                                "search_clicked": True
                            },
                            "sessionId": "debug-session",
                            "hypothesisId": "A"
                        }) + '\n')
                except Exception as log_e:
                    logger.debug(f"Debug log failed: {log_e}")
                # #endregion
                
            except Exception as e:
                logger.warning(f"Search butonuna tıklanamadı (devam ediliyor): {e}")
                time.sleep(3)
                
                # #region agent log
                # DEBUG: Search başarısız - buton bulunamadı
                try:
                    import json
                    debug_log_path = '/app/debug.log'
                    with open(debug_log_path, 'a') as f:
                        f.write(json.dumps({
                            "timestamp": int(time.time() * 1000),
                            "location": "tiktok_selenium_scraper.py:555",
                            "message": "Search button click failed",
                            "data": {
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "search_clicked": False
                            },
                            "sessionId": "debug-session",
                            "hypothesisId": "A"
                        }) + '\n')
                except Exception as log_e:
                    logger.debug(f"Debug log failed: {log_e}")
                # #endregion
            
            # "VIEW MORE" BUTTON CLICKING: TikTok'un pagination stratejisi
            logger.info(f"'View more' butonu ile daha fazla reklam yükleniyor (hedef: {max_ads_per_search})...")
            
            # İlk scroll (View more butonunu görmek için)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # View more butonuna basarak reklam yükleme
            view_more_clicks = 0
            max_view_more_clicks = 10  # Maksimum 10 kere tıkla (güvenlik için)
            
            while view_more_clicks < max_view_more_clicks:
                try:
                    # Mevcut reklam sayısını kontrol et
                    current_ad_count = len(self.driver.find_elements(By.CSS_SELECTOR, '.ad_card, div[class*="ad_card"]'))
                    
                    # Hedef sayıya ulaştıysak dur
                    if current_ad_count >= max_ads_per_search:
                        logger.info(f"✅ Hedef reklam sayısına ulaşıldı: {current_ad_count} >= {max_ads_per_search}")
                        break
                    
                    # View more butonunu bul
                    view_more_selectors = [
                        "//span[@class='loading_more_text']",  # Ana selector
                        "//span[contains(@class, 'loading_more_text')]",
                        "//span[text()='View more']",
                        "//div[@class='loading_more']",
                        "//div[contains(@class, 'loading_more')]"
                    ]
                    
                    view_more_button = None
                    for selector in view_more_selectors:
                        try:
                            view_more_button = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                            if view_more_button:
                                logger.info(f"✓ View more butonu bulundu (selector: {selector})")
                                break
                        except:
                            continue
                    
                    if not view_more_button:
                        logger.info("View more butonu bulunamadı, tüm reklamlar yüklendi")
                        break
                    
                    # Butona tıkla
                    try:
                        view_more_button.click()
                        view_more_clicks += 1
                        logger.info(f"🖱️  View more'a tıklandı ({view_more_clicks}. tıklama)")
                    except:
                        # JavaScript ile tıkla
                        self.driver.execute_script("arguments[0].click();", view_more_button)
                        view_more_clicks += 1
                        logger.info(f"🖱️  View more'a JavaScript ile tıklandı ({view_more_clicks}. tıklama)")
                    
                    # Yeni reklamların yüklenmesini bekle (kullanıcı 7-8 saniye dedi, güvenli olması için 10)
                    logger.info("⏳ Yeni reklamlar yükleniyor (10 saniye bekleniyor)...")
                    time.sleep(10)
                    
                    # Yeni reklamlar yüklendi mi kontrol et
                    new_ad_count = len(self.driver.find_elements(By.CSS_SELECTOR, '.ad_card, div[class*="ad_card"]'))
                    
                    # #region agent log
                    import json
                    try:
                        with open('/app/debug.log', 'a') as f:
                            f.write(json.dumps({
                                "timestamp": int(time.time() * 1000),
                                "location": "tiktok_selenium_scraper.py:650",
                                "message": "View more clicked",
                                "data": {
                                    "click_count": view_more_clicks,
                                    "ads_before": current_ad_count,
                                    "ads_after": new_ad_count,
                                    "new_ads_loaded": new_ad_count - current_ad_count,
                                    "target": max_ads_per_search
                                },
                                "sessionId": "debug-session",
                                "runId": "test",
                                "hypothesisId": "H8"
                            }) + '\n')
                    except: pass
                    # #endregion
                    
                    if new_ad_count == current_ad_count:
                        logger.warning("⚠️  Yeni reklam yüklenmedi, döngü sonlandırılıyor")
                        break
                    
                    logger.info(f"✅ {new_ad_count - current_ad_count} yeni reklam yüklendi (Toplam: {new_ad_count})")
                    
                    # View more butonu için tekrar scroll
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    
                except Exception as e:
                    logger.warning(f"View more tıklama hatası: {e}")
                    break
            
            logger.info(f"🎉 View more işlemi tamamlandı: {view_more_clicks} tıklama yapıldı")
            
            # DEBUG: Screenshot + Network logs kaydet
            try:
                screenshot_path = '/app/debug_screenshot.png'
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"Screenshot kaydedildi: {screenshot_path}")
                
                # Network logs (performance logs)
                network_logs = self.driver.get_log('performance')
                import json
                network_path = '/app/debug_network.json'
                with open(network_path, 'w') as f:
                    json.dump(network_logs, f, indent=2)
                logger.info(f"Network logs kaydedildi: {network_path} ({len(network_logs)} entries)")
            except Exception as debug_e:
                logger.warning(f"Debug dosyaları kaydedilemedi: {debug_e}")
            
            # Reklam kartlarını bul
            ad_elements = self._find_ad_elements()
            
            if not ad_elements:
                logger.warning("Reklam bulunamadı, sayfa yapısı değişmiş olabilir")
                return []
            
            logger.info(f"{len(ad_elements)} reklam elementi bulundu")
            
            # #region agent log
            try:
                import json
                with open('/app/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "timestamp": int(time.time() * 1000),
                        "location": "tiktok_selenium_scraper.py:690",
                        "message": "Ad elements found before extraction",
                        "data": {
                            "total_elements_found": len(ad_elements),
                            "max_ads_per_search": max_ads_per_search,
                            "will_extract": min(len(ad_elements), max_ads_per_search)
                        },
                        "sessionId": "debug-session",
                        "runId": "test",
                        "hypothesisId": "H6"
                    }) + '\n')
            except: pass
            # #endregion
            
            # Her reklam için detay çıkar
            for i, ad_element in enumerate(ad_elements[:max_ads_per_search]):
                try:
                    ad_data = self._extract_ad_data(ad_element, i)
                    if ad_data:
                        ads.append(ad_data)
                        
                except Exception as e:
                    logger.warning(f"Reklam {i+1} işlenirken hata: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"URL scraping hatası: {e}")
        
        return ads
    
    def _find_ad_elements(self) -> List:
        """Sayfadaki reklam elementlerini bul - TikTok güncel yapısı"""
        try:
            # Önce sayfanın tam yüklenmesini bekle - UZUN BEKLE (TikTok yavaş yüklenebilir)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # JavaScript'in çalışması ve reklamların yüklenmesi için kısa bekle
            # (Çünkü _scrape_ads_from_url zaten agresif scroll yaptı)
            logger.info("Reklamların DOM'a yüklenmesini bekliyorum...")
            time.sleep(2)
            
            # Scroll to top to ensure we catch all elements
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            logger.info("Elementleri arıyorum...")
            
            # #region agent log
            # DEBUG: Scroll sonrası sayfa durumu
            try:
                import json
                debug_log_path = '/app/debug.log'
                page_title = self.driver.title
                current_url = self.driver.current_url
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                body_text_len = len(body_text)
                
                # Total ads değeri
                total_ads_text = "not_found"
                try:
                    total_elem = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Total ads')]")
                    total_ads_text = total_elem.text
                except:
                    pass
                
                with open(debug_log_path, 'a') as f:
                    f.write(json.dumps({
                        "timestamp": int(time.time() * 1000),
                        "location": "tiktok_selenium_scraper.py:695",
                        "message": "Pre-selector page state",
                        "data": {
                            "page_title": page_title,
                            "url": current_url,
                            "body_text_length": body_text_len,
                            "total_ads_text": total_ads_text,
                            "body_contains_qnb": "QNB" in body_text,
                            "body_contains_ing": "ING" in body_text
                        },
                        "sessionId": "debug-session",
                        "hypothesisId": "B"
                    }) + '\n')
            except Exception as log_e:
                logger.debug(f"Debug log failed: {log_e}")
            # #endregion
            
            # Öncelikli selector'lar - TikTok'un gerçek reklam kartlarını bul
            selectors = [
                '.ad_card',  # Öncelik 1: TikTok'un gerçek reklam kartı class'ı
                'div[class*="ad_card"]',  # Öncelik 2: ad_card içeren div
                'div[class*="AdCard"]',  # Öncelik 3: AdCard içeren div
                'div[data-testid*="ad"]',  # Öncelik 4: data-testid ile
                'div[class*="ad"]'  # Fallback: Genel ad içeren div
            ]
            
            for selector in selectors:
                try:
                    found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if found:
                        logger.debug(f"Selector {selector} ile {len(found)} element bulundu")
                        
                        # UI elementlerini filtrele - gerçek reklam kartlarını bul
                        filtered = []
                        for idx, elem in enumerate(found):
                            try:
                                text = elem.text.strip()
                                
                                # Boş elementleri atla
                                if not text:
                                    continue
                                
                                # Sadece AÇIKÇA form alanı olanları atla (küçük liste)
                                form_text_lower = text.lower().strip()
                                skip_keywords = ['target country', 'advertiser name or keyword', 'english (us)', 'search']
                                if form_text_lower in skip_keywords:
                                    logger.debug(f"Element {idx}: Form alanı '{text[:30]}', atlandı")
                                    continue
                                
                                # Çok kısa text'leri atla (10 karakter)
                                if len(text) < 10:
                                    continue
                                
                                # Link/media kontrolü - SIKLAŞTIRILMIŞ
                                # Sadece TikTok reklam içeriği (ibyteimg CDN)
                                has_link = len(elem.find_elements(By.CSS_SELECTOR, 'a[href*="detail"], a[href*="ad_id"]')) > 0
                                has_real_media = len(elem.find_elements(By.CSS_SELECTOR, 'video, img[src*="ibyteimg"]')) > 0
                                
                                logger.debug(f"Element {idx}: text='{text[:50]}', len={len(text)}, has_link={has_link}, has_real_media={has_real_media}")
                                
                                # SIKLAŞTIRILMIŞ: has_link ZORUNLU (media yeterli değil, logo/icon olabilir)
                                if has_link:
                                    filtered.append(elem)
                                    logger.info(f"✓ Element {idx} KABUL: reklam linki var")
                                # Fallback: Gerçek media (ibyteimg CDN) + uzun text (100+)
                                elif has_real_media and len(text) > 100:
                                    filtered.append(elem)
                                    logger.info(f"✓ Element {idx} KABUL: TikTok CDN media + uzun text")
                                else:
                                    logger.debug(f"✗ Element {idx} RED: link yok (media: {has_real_media}, len: {len(text)})")
                                    
                            except Exception as e:
                                logger.debug(f"Element {idx} hatası: {e}")
                                continue
                        
                        if filtered:
                            logger.info(f"✅ {len(filtered)} gerçek reklam kartı bulundu (selector: {selector})")
                            return filtered
                        else:
                            logger.debug(f"Selector {selector}: Filtreleme sonrası 0 element kaldı")
                except Exception as e:
                    logger.debug(f"Selector {selector} ile hata: {e}")
                    continue
            
            logger.warning("Hiçbir reklam elementi bulunamadı")
            # Debug için sayfa kaynağını kaydet
            try:
                page_source = self.driver.page_source
                debug_path = Path(__file__).parent.parent.parent / 'debug_page_source.html'
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(page_source)
                logger.info(f"Debug: Sayfa kaynağı '{debug_path}' dosyasına kaydedildi")
            except Exception as debug_e:
                logger.debug(f"Debug dosyası kaydedilemedi: {debug_e}")
                return []
            
        except Exception as e:
            logger.error(f"Element bulma hatası: {e}")
            return []
    
    def _extract_ad_data(self, ad_element, index: int) -> Optional[Dict]:
        """Reklam elementinden veri çıkar"""
        try:
            ad_data = {
                'scrape_index': index,
                'scraped_at': datetime.now().isoformat(),
                'advertiser_name': 'Unknown',
                'ad_text': '',
                'media_urls': [],
                'ad_url': '',
                'first_shown': '',
                'last_shown': '',
                'reach': ''
            }
            
            # Selenium element ise
            if hasattr(ad_element, 'find_element'):
                ad_data.update(self._extract_from_selenium_element(ad_element))
            else:
                # BeautifulSoup element ise
                ad_data.update(self._extract_from_bs_element(ad_element))
            
            # Temel doğrulama
            if not ad_data.get('advertiser_name') or ad_data['advertiser_name'] == 'Unknown':
                logger.warning(f"Reklam {index}: Advertiser name bulunamadı")
            
            return ad_data
            
        except Exception as e:
            logger.warning(f"Reklam {index} veri çıkarma hatası: {e}")
            return None
    
    def _extract_from_selenium_element(self, element) -> Dict:
        """Hızlı test versiyonu - Video extraction atlanıyor (çok yavaş)"""
        data = {}
        
        try:
            # #region agent log
            try:
                with open("/app/debug.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "video-debug-1",
                        "hypothesisId": "A",
                        "location": "tiktok_selenium_scraper.py:_extract_from_selenium_element:start",
                        "message": "Fast test mode active; detail-page video extraction is skipped",
                        "data": {
                            "fast_test_mode": True,
                            "tag_name": getattr(element, "tag_name", None),
                            "class_attr": (element.get_attribute("class") or "")[:120]
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception:
                pass
            # #endregion

            # TEST İÇİN: Video extraction'ı atla (çok yavaş - detay sayfasına gitmek 15+ saniye sürüyor)
            # Sadece thumbnail ve metadata çıkar
                data.update(self._original_media_extraction(element))
            data.update(self._extract_ad_metadata(element))
            data['extraction_method'] = 'fast_test_mode'

            # #region agent log
            try:
                with open("/app/debug.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "video-debug-1",
                        "hypothesisId": "B",
                        "location": "tiktok_selenium_scraper.py:_extract_from_selenium_element:after_media",
                        "message": "Media extraction result (fast mode)",
                        "data": {
                            "media_type": data.get("media_type"),
                            "media_urls_count": len(data.get("media_urls", [])),
                            "first_media_url": (data.get("media_urls") or [None])[0]
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            
        except Exception as e:
            logger.error(f"Extraction hatası: {e}")
            data.update(self._extract_ad_metadata(element))
        
        return data

    def _trigger_main_page_video_load(self, element):
        """Ana sayfadaki video yüklemeyi tetikle"""
        try:
            # Video player'a hover et
            video_player = element.find_element(By.CSS_SELECTOR, '.video_player')
            self.driver.execute_script("""
                arguments[0].dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                arguments[0].dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
            """, video_player)
            
            time.sleep(1)
            
            # Click et
            self.driver.execute_script("arguments[0].click();", video_player)
            
            time.sleep(2)
            
        except Exception as e:
            logger.debug(f"Video trigger hatası: {e}")

    def _extract_ad_metadata(self, element) -> Dict:
        """Reklam meta verilerini çıkar - TikTok'un gerçek yapısı"""
        data = {}
        
        try:
            # Advertiser name - SPESİFİK selector kullan: .ad_info_text
            try:
                # İlk önce en spesifik selector'ı dene (.ad_info_text)
                advertiser_elem = element.find_element(By.CSS_SELECTOR, '.ad_info_text')
                advertiser_text = clean_text(advertiser_elem.text).strip()
                
                if advertiser_text and len(advertiser_text) > 2:
                    data['advertiser_name'] = advertiser_text
                    logger.debug(f"✓ Advertiser name bulundu (.ad_info_text): {advertiser_text}")
                else:
                    data['advertiser_name'] = 'Unknown'
            except:
                # Fallback: .ad_info_name kullan ve "Ad" badge'ini temizle
                try:
                    advertiser_elem = element.find_element(By.CSS_SELECTOR, '.ad_info_name')
                    advertiser_text = clean_text(advertiser_elem.text)
                    # "Ad" kelimesini kaldır (başta, sonda veya ayrı satırda olabilir)
                    lines = advertiser_text.split('\n')
                    # "Ad" satırını atla, diğer satırları birleştir
                    filtered_lines = [line.strip() for line in lines if line.strip().lower() != 'ad' and len(line.strip()) > 2]
                    if filtered_lines:
                        advertiser_text = ' '.join(filtered_lines).strip()
                    else:
                        # Eğer tek satırsa, "Ad " ile başlıyorsa kaldır
                        advertiser_text = advertiser_text.replace('Ad ', '').replace('Ad ', '').strip()
                        # Başta veya sonda "Ad" kelimesi varsa kaldır
                        if advertiser_text.lower().startswith('ad '):
                            advertiser_text = advertiser_text[3:].strip()
                        if advertiser_text.lower().endswith(' ad'):
                            advertiser_text = advertiser_text[:-3].strip()
                    
                    # Son bir temizleme: Başta "Ad " varsa kaldır (case-insensitive)
                    if advertiser_text:
                        # Regex ile başta "Ad " veya "ad " kaldır
                        advertiser_text = re.sub(r'^[Aa][Dd]\s+', '', advertiser_text).strip()
                    
                    if advertiser_text and len(advertiser_text) > 2:
                        data['advertiser_name'] = advertiser_text
                        logger.debug(f"✓ Advertiser name bulundu (.ad_info_name fallback): {advertiser_text}")
                    else:
                        data['advertiser_name'] = 'Unknown'
                except:
                    # Fallback: Text içinden bul
                    try:
                        full_text = element.text
                        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                        # "Ad" kelimesinden sonraki satır genelde advertiser name
                        for i, line in enumerate(lines):
                            if line.lower() == 'ad' and i + 1 < len(lines):
                                next_line = lines[i + 1].strip()
                                if len(next_line) > 2 and len(next_line) < 200:
                                    advertiser_name = clean_text(next_line)
                                    # "Ad " ile başlıyorsa kaldır
                                    if advertiser_name.lower().startswith('ad '):
                                        advertiser_name = advertiser_name[3:].strip()
                                    data['advertiser_name'] = advertiser_name
                                    break
                        # Eğer bulunamadıysa, ilk anlamlı satırı al ve "Ad " ile başlıyorsa temizle
                        if not data.get('advertiser_name'):
                            for line in lines:
                                if len(line) > 5:  # Anlamlı bir satır
                                    advertiser_name = clean_text(line)
                                    # "Ad " ile başlıyorsa kaldır
                                    if advertiser_name.lower().startswith('ad '):
                                        advertiser_name = advertiser_name[3:].strip()
                                    if len(advertiser_name) > 2:
                                        data['advertiser_name'] = advertiser_name
                                        break
                        if not data.get('advertiser_name'):
                            data['advertiser_name'] = 'Unknown'
                    except:
                        data['advertiser_name'] = 'Unknown'
            
            # Ad details - tarih ve reach bilgileri (text içinde)
            try:
                detail_text = element.text
                lines = detail_text.split('\n')
                for i, line in enumerate(lines):
                    line = line.strip()
                    if 'First shown:' in line:
                        # Sonraki satır tarih olabilir
                        if i + 1 < len(lines):
                            data['first_shown'] = lines[i + 1].strip()
                        else:
                            data['first_shown'] = line.replace('First shown:', '').strip()
                    elif 'Last shown:' in line:
                        if i + 1 < len(lines):
                            data['last_shown'] = lines[i + 1].strip()
                        else:
                            data['last_shown'] = line.replace('Last shown:', '').strip()
                    elif 'Unique users seen:' in line:
                        if i + 1 < len(lines):
                            data['reach'] = lines[i + 1].strip()
                        else:
                            data['reach'] = line.replace('Unique users seen:', '').strip()
            except:
                pass
            
            # Ad ID ve detail URL - a.link class'ı kullan
            try:
                link_elem = element.find_element(By.CSS_SELECTOR, 'a.link')
                href = link_elem.get_attribute('href')
                if href:
                    # Tam URL yap
                    if href.startswith('/'):
                        href = f"https://library.tiktok.com{href}"
                    data['ad_url'] = href
                    
                    # Ad ID'yi URL'den çıkar
                    if 'ad_id=' in href:
                        ad_id = href.split('ad_id=')[1].split('&')[0]
                        data['ad_id'] = ad_id
            except:
                # Fallback: Herhangi bir link ara
                try:
                    link_elems = element.find_elements(By.CSS_SELECTOR, 'a[href*="detail"]')
                    for link_elem in link_elems:
                        href = link_elem.get_attribute('href')
                        if href and 'ad_id=' in href:
                            if href.startswith('/'):
                                href = f"https://library.tiktok.com{href}"
                            data['ad_url'] = href
                            ad_id = href.split('ad_id=')[1].split('&')[0]
                            data['ad_id'] = ad_id
                            break
                except:
                    pass
            
            # Ad text - sadece advertiser name'i al (reklam metni detay sayfasında)
            # Ana sayfada genelde sadece advertiser name var
            data['ad_text'] = data.get('advertiser_name', '')
        
        except Exception as e:
            logger.debug(f"Metadata extraction hatası: {e}")
        
        return data

    def _original_media_extraction(self, element) -> Dict:
        """Media extraction - Güncel TikTok yapısı"""
        data = {
            'media_urls': [],
            'media_type': 'text',
            'video_found': False,
            'extraction_method': 'fallback_original'
        }
        
        try:
            # İlk görünürlük için sayım
            try:
                video_count = len(element.find_elements(By.CSS_SELECTOR, 'video'))
                img_count = len(element.find_elements(By.CSS_SELECTOR, 'img'))
            except Exception:
                video_count = -1
                img_count = -1

            # #region agent log
            try:
                with open("/app/debug.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "video-debug-1",
                        "hypothesisId": "D",
                        "location": "tiktok_selenium_scraper.py:_original_media_extraction:counts",
                        "message": "Base media element counts on ad card",
                        "data": {
                            "video_elements": video_count,
                            "image_elements": img_count
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception:
                pass
            # #endregion

            # Video elementlerini bul
            video_selectors = [
                'video',
                '[class*="video"]',
                '[class*="Video"]',
                '[data-testid*="video"]',
            ]
            
            for selector in video_selectors:
                try:
                    videos = element.find_elements(By.CSS_SELECTOR, selector)
                    for video in videos:
                        video_url = None
                        
                        # 1. Önce <source> tag'lerini kontrol et (en güvenilir)
                        try:
                            sources = video.find_elements(By.TAG_NAME, 'source')
                            for source in sources:
                                src = source.get_attribute('src')
                                if src and ('ibyteimg.com' in src or '.mp4' in src.lower() or 'video' in src.lower()):
                                    video_url = src
                                    logger.info(f"✅ Video URL <source> tag'inden bulundu: {src[:100]}...")
                                    break
                        except:
                            pass
                        
                        # 2. Video tag'inin src attribute'ü (ikinci seçenek)
                        if not video_url:
                            src = video.get_attribute('src')
                            if src and ('ibyteimg.com' in src or '.mp4' in src.lower() or 'video' in src.lower()):
                                # URL'nin gerçekten video olup olmadığını kontrol et
                                if not src.endswith('.jpg') and not src.endswith('.jpeg') and not src.endswith('.png'):
                                    video_url = src
                                    logger.info(f"✅ Video URL video.src'den bulundu: {src[:100]}...")
                        
                        # 3. data-src, data-video-url gibi attribute'leri kontrol et
                        if not video_url:
                            for attr in ['data-src', 'data-video-url', 'data-url', 'data-video']:
                                src = video.get_attribute(attr)
                                if src and 'ibyteimg.com' in src:
                                    if not src.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                                        video_url = src
                                        logger.info(f"✅ Video URL {attr} attribute'ünden bulundu: {src[:100]}...")
                                        break
                        
                        # 4. Poster attribute kontrolü - SADECE gerçek video bulunamazsa
                        # NOT: Poster thumbnail'dir, gerçek video DEĞİL!
                        if not video_url:
                            poster = video.get_attribute('poster')
                            if poster and 'ibyteimg.com' in poster:
                                # Poster'ı KULLANMA - media_type'ı image yap
                                logger.warning(f"⚠️ Sadece poster (thumbnail/image) bulundu, gerçek video yok: {poster[:100]}...")
                                # Poster'ı media_urls'e ekle ama media_type'ı image yap
                                data['media_urls'].append(poster)
                                data['media_type'] = 'image'  # Video değil, image!
                                break  # Loop'tan çık, image bulundu
                        
                        if video_url:
                            data['media_urls'].append(video_url)
                            data['media_type'] = 'video'
                            data['video_found'] = True
                            # #region agent log
                            try:
                                with open("/app/debug.log", "a", encoding="utf-8") as f:
                                    f.write(json.dumps({
                                        "sessionId": "debug-session",
                                        "runId": "video-debug-1",
                                        "hypothesisId": "C",
                                        "location": "tiktok_selenium_scraper.py:_original_media_extraction:video_found",
                                        "message": "Video URL found from DOM element",
                                        "data": {
                                            "selector": selector,
                                            "src": video_url[:160] if video_url else None,
                                            "tag_name": video.tag_name,
                                            "has_source_tags": len(video.find_elements(By.TAG_NAME, 'source')) > 0
                                        },
                                        "timestamp": int(time.time() * 1000)
                                    }) + "\n")
                            except Exception:
                                pass
                            # #endregion
                            break
                    if data['video_found']:
                        break
                except:
                    continue
            
            # Image elementlerini bul
            if not data['video_found']:
                image_selectors = [
                    'img',
                    '[class*="image"]',
                    '[class*="Image"]',
                    '[class*="thumbnail"]',
                    '[data-testid*="image"]',
                ]
                
                for selector in image_selectors:
                    try:
                        images = element.find_elements(By.CSS_SELECTOR, selector)
                        for img in images:
                            src = img.get_attribute('src')
                            if src:
                                # Placeholder SVG'leri filtrele (data:image/svg+xml)
                                if src.startswith('data:image/svg+xml'):
                                    continue
                                # Gerçek image URL'leri kabul et
                                if ('image' in src.lower() or any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', 'http', 'https'])):
                                    data['media_urls'].append(src)
                                    data['media_type'] = 'image'
                                    logger.info(f"✅ Image URL bulundu: {src[:100]}...")
                                    # #region agent log
                                    try:
                                        looks_like_video = ('video' in src.lower() or '.mp4' in src.lower())
                                        looks_like_thumb = bool(re.search(r'(thumb|poster|preview|cover|ibyteimg)', src, re.IGNORECASE))
                                        with open("/app/debug.log", "a", encoding="utf-8") as f:
                                            f.write(json.dumps({
                                                "sessionId": "debug-session",
                                                "runId": "video-debug-1",
                                                "hypothesisId": "B",
                                                "location": "tiktok_selenium_scraper.py:_original_media_extraction:image_found",
                                                "message": "Image URL chosen (possible thumbnail)",
                                                "data": {
                                                    "selector": selector,
                                                    "src": src[:160],
                                                    "looks_like_video": looks_like_video,
                                                    "looks_like_thumbnail": looks_like_thumb
                                                },
                                                "timestamp": int(time.time() * 1000)
                                            }) + "\n")
                                    except Exception:
                                        pass
                                    # #endregion
                                    break
                        if data['media_urls']:
                            break
                    except:
                        continue
            
            # Background image extraction (fallback)
            if not data['media_urls']:
                try:
                    # İlk önce .video_player class'ını dene (en yaygın)
                    # ÖNEMLİ: .video_player TikTok'ta VIDEO thumbnail'ı için kullanılır!
                    video_players = element.find_elements(By.CSS_SELECTOR, '.video_player')
                    for video_player in video_players:
                        style = video_player.get_attribute('style')
                        if style and 'background-image' in style:
                            # URL'i çıkar (HTML entities decoded olmalı)
                            url_match = re.search(r'background-image:\s*url\(["\']?(.*?)["\']?\)', style)
                            if url_match:
                                media_url = url_match.group(1).strip()
                                # Placeholder SVG'leri ve base64'leri filtrele
                                if (media_url and 
                                    media_url != 'none' and 
                                    not media_url.startswith('data:image/svg+xml') and
                                    'ibyteimg.com' in media_url):  # TikTok CDN kontrolü
                                    
                                    # Content-Type kontrolü yap (gerçek media type'ı bul)
                                    actual_type = check_url_content_type(media_url, timeout=3)
                                    
                                    data['media_urls'].append(media_url)
                                    
                                    # Gerçek Content-Type'a göre media_type belirle
                                    if actual_type == 'video':
                                        data['media_type'] = 'video'
                                        data['video_found'] = True
                                        logger.info(f"✅ VIDEO (confirmed by Content-Type): {media_url[:80]}...")
                                    elif actual_type == 'image':
                                        # .video_player'dan geldi ama aslında image (thumbnail)
                                        data['media_type'] = 'image'
                                        logger.warning(f"⚠️ .video_player'dan IMAGE bulundu (thumbnail): {media_url[:80]}...")
                                    else:
                                        # Content-Type belirsiz - .video_player class'ına güven
                                        data['media_type'] = 'video'
                                        data['video_found'] = True
                                        logger.info(f"✅ VIDEO (assumed from .video_player class): {media_url[:80]}...")
                                    
                                    break  # İlk media yeterli
                    
                    # Fallback: Tüm elementlerde background-image ara (bu sefer IMAGE olarak)
                    if not data['media_urls']:
                        all_elements = element.find_elements(By.CSS_SELECTOR, '*')
                        for elem in all_elements:
                            style = elem.get_attribute('style')
                            if style and 'background-image' in style:
                                url_match = re.search(r'background-image:\s*url\(["\']?(.*?)["\']?\)', style)
                                if url_match:
                                    media_url = url_match.group(1).strip()
                                    # Placeholder SVG'leri filtrele
                                    if media_url and media_url != 'none' and not media_url.startswith('data:image/svg+xml'):
                                        data['media_urls'].append(media_url)
                                        # Generic background-image → muhtemelen gerçek bir IMAGE
                                        data['media_type'] = 'image'
                                        logger.info(f"✅ Background image URL bulundu (image): {media_url[:80]}...")
                                        break
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Media extraction hatası: {e}")
        
        return data
        
        return data
    
    def _extract_from_bs_element(self, element) -> Dict:
        """BeautifulSoup elementinden veri çıkar"""
        data = {}
        
        try:
            # Text içeriğini al
            text_content = element.get_text(strip=True)
            if len(text_content) > 20:  # Anlamlı içerik varsa
                data['ad_text'] = clean_text(text_content[:200])
            
            # Images
            images = element.find_all('img')
            data['media_urls'] = [img.get('src') for img in images if img.get('src')]
            
            # Links
            links = element.find_all('a', href=True)
            if links:
                data['ad_url'] = links[0]['href']
                
        except Exception as e:
            logger.debug(f"BeautifulSoup extraction error: {e}")
        
        return data
    
    def save_screenshot(self, filename: str = None):
        """Debug için screenshot al"""
        if not self.driver:
            return
            
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/debug/screenshot_{timestamp}.png"
        
        try:
            import os
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            self.driver.save_screenshot(filename)
            logger.info(f"Screenshot kaydedildi: {filename}")
        except Exception as e:
            logger.error(f"Screenshot kaydetme hatası: {e}")