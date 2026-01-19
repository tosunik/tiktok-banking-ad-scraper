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
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from loguru import logger

from src.config.settings import settings
from src.utils.helpers import safe_sleep, clean_text
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
                        region: str = "TR",
                        days_back: int = 30) -> str:
        """TikTok Ad Library arama URL'i oluştur"""
        
        # Tarih aralığı hesapla (Unix timestamp milisaniye)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        
        start_timestamp = int(start_time.timestamp() * 1000)
        end_timestamp = int(end_time.timestamp() * 1000)
        
        url = f"{self.base_url}/ads"
        params = [
            f"region={region}",
            f"start_time={start_timestamp}",
            f"end_time={end_timestamp}",
            f"adv_name={advertiser_name}" if advertiser_name else "adv_name=",
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
            for advertiser in advertiser_names:
                logger.info(f"'{advertiser}' reklamları aranıyor...")
                
                search_url = self.build_search_url(advertiser_name=advertiser)
                logger.info(f"URL: {search_url}")
                
                ads = self._scrape_ads_from_url(search_url, max_ads_per_search=3)  # 20'den 3'e düşürüldü
                all_ads.extend(ads)
                
                logger.info(f"'{advertiser}' için {len(ads)} reklam bulundu")
                
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
        """Türk bankalarının reklamlarını ara"""
        
        # Türk bankaları listesi
        turkish_banks = [
            "garanti", "isbank", "yapikredi", "akbank", "halkbank", "vakifbank",
            "denizbank", "ingbank", "teb", "finansbank", "kuveytturk", "albaraka",
            "papara", "ininal", "tosla", "param", "ziraat", "enpara"
        ]
        
        return self.search_ads_by_advertiser(turkish_banks, max_ads)
    
    def _scrape_ads_from_url(self, url: str, max_ads_per_search: int = 3) -> List[Dict]:
        """Belirli URL'den reklamları scrape et - Hızlı test versiyonu"""
        ads = []
        
        try:
            self.driver.get(url)
            
            # Sayfanın yüklenmesini bekle (20'den 8'e düşürüldü)
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Dinamik içerik için bekle (10'dan 3'e düşürüldü)
            time.sleep(3)
            
            # Scroll yaparak içeriği yükle (beklemeleri azalt)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)  # 3'ten 1'e düşürüldü
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # 3'ten 2'ye düşürüldü
            
            # Reklam kartlarını bul
            ad_elements = self._find_ad_elements()
            
            if not ad_elements:
                logger.warning("Reklam bulunamadı, sayfa yapısı değişmiş olabilir")
                return []
            
            logger.info(f"{len(ad_elements)} reklam elementi bulundu")
            
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
            # Önce sayfanın tam yüklenmesini bekle (15'ten 8'e düşürüldü)
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # JavaScript'in çalışması için bekle (5'ten 2'ye düşürüldü)
            time.sleep(2)
            
            # Scroll yaparak dinamik içeriği yükle (beklemeleri azalt)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)  # 2'den 1'e düşürüldü
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # 3'ten 2'ye düşürüldü
            
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
                        # UI elementlerini filtrele - gerçek reklam kartlarını bul
                        filtered = []
                        for elem in found:
                            text = elem.text.strip()
                            # En az 10 karakter içerik olmalı ve UI metinlerini atla
                            if text and len(text) > 10:
                                # "Filters", "Search results", "Total ads: 0" gibi UI metinlerini atla
                                ui_keywords = ['Filters', 'Search results', 'Total ads:', 'Sort by', 'Region:', 'Date range:']
                                if not any(ui_keyword in text for ui_keyword in ui_keywords):
                                    filtered.append(elem)
                        
                        if filtered:
                            logger.info(f"✅ {len(filtered)} reklam elementi bulundu (selector: {selector})")
                            return filtered
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
            # TEST İÇİN: Video extraction'ı atla (çok yavaş - detay sayfasına gitmek 15+ saniye sürüyor)
            # Sadece thumbnail ve metadata çıkar
            data.update(self._original_media_extraction(element))
            data.update(self._extract_ad_metadata(element))
            data['extraction_method'] = 'fast_test_mode'
            
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
            # Advertiser name - .ad_info_name class'ı kullan
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
                        src = video.get_attribute('src')
                        if src and ('video' in src.lower() or '.mp4' in src.lower()):
                            data['media_urls'].append(src)
                            data['media_type'] = 'video'
                            data['video_found'] = True
                            logger.info(f"✅ Video URL bulundu: {src[:100]}...")
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
                                    break
                        if data['media_urls']:
                            break
                    except:
                        continue
            
            # Background image extraction (fallback)
            if not data['media_urls']:
                try:
                    # Tüm elementlerde background-image ara
                    all_elements = element.find_elements(By.CSS_SELECTOR, '*')
                    for elem in all_elements:
                        style = elem.get_attribute('style')
                        if style and 'background-image' in style:
                            url_match = re.search(r'background-image:\s*url\(["\']?(.*?)["\']?\)', style)
                            if url_match:
                                media_url = url_match.group(1)
                                # Placeholder SVG'leri filtrele
                                if media_url and media_url != 'none' and not media_url.startswith('data:image/svg+xml'):
                                    data['media_urls'].append(media_url)
                                    data['media_type'] = 'image'
                                    logger.info(f"✅ Background image URL bulundu: {media_url[:100]}...")
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