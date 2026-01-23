import requests
import time
import json
from typing import List, Dict, Optional, Any
from loguru import logger
from datetime import datetime
import re
from pathlib import Path

from src.config.settings import settings
from src.models.ad_model import TikTokAd, MediaType, AdStatus, ScrapingResult
from src.utils.helpers import is_banking_related, clean_text, safe_sleep, create_filename_safe

from src.scraper.tiktok_selenium_scraper import TikTokSeleniumScraper

class TikTokAdScraper:
    """TikTok Ad Library Scraper - Selenium ile Türkiye odaklı"""
    
    def __init__(self, headless: bool = True):
        self.selenium_scraper = TikTokSeleniumScraper(headless=headless)
        self.scraped_ads = []
        self.seen_ad_hashes = set()  # Duplicate detection için
        
    def search_ads(self, 
                   keywords: List[str], 
                   max_results: int = 200, 
                   search_type: str = "keyword",
                   advertiser_blacklist: Optional[List[str]] = None,
                   advertiser_whitelist: Optional[List[str]] = None) -> ScrapingResult:
        """TikTok'ta reklam ara - Selenium ile
        
        Args:
            keywords: Aranacak kelimeler
            max_results: Maksimum reklam sayısı
            search_type: "keyword" = genel arama, "advertiser" = şirket adı araması
            advertiser_blacklist: Hariç tutulacak advertiser'lar (örn: ['QNB', 'ING'])
            advertiser_whitelist: Sadece dahil edilecek advertiser'lar (örn: ['GARANTI', 'AKBANK'])
        """
        result = ScrapingResult()
        
        try:
            logger.info(f"Selenium ile TikTok scraping başlatılıyor... Keywords: {keywords}, Search type: {search_type}")
            
            # Keywords parametresini kullan
            if keywords and len(keywords) > 0:
                if search_type == "keyword":
                    # KEYWORD SEARCH: Reklam içeriğinde ara (daha geniş)
                    logger.info(f"KEYWORD araması: {keywords}")
                    raw_ads_data = self.selenium_scraper.search_ads_by_keyword(keywords, max_results)
                else:
                    # ADVERTISER SEARCH: Şirket adında ara (dar)
                    logger.info(f"ADVERTISER araması: {keywords}")
                    raw_ads_data = self.selenium_scraper.search_ads_by_advertiser(keywords, max_results)
            else:
                # Keywords yoksa tüm bankaları ara (fallback)
                raw_ads_data = self.selenium_scraper.search_banking_ads(max_results)
            
            logger.info(f"Raw data alındı: {len(raw_ads_data)} reklam")
            
            # Reklamları işle ve filtrele
            filtered_count = 0
            for ad_data in raw_ads_data:
                try:
                    ad = self._create_ad_from_selenium_data(ad_data)
                    if not ad:
                        continue
                    
                    advertiser_name = (ad.advertiser_name or "").upper()
                    
                    # BLACKLIST kontrolü (önce)
                    if advertiser_blacklist:
                        is_blacklisted = any(
                            blacklisted.upper() in advertiser_name 
                            for blacklisted in advertiser_blacklist
                        )
                        if is_blacklisted:
                            logger.debug(f"Reklam blacklist nedeniyle filtrelendi: {ad.advertiser_name}")
                            filtered_count += 1
                            continue
                    
                    # WHITELIST kontrolü (sonra)
                    if advertiser_whitelist:
                        is_whitelisted = any(
                            whitelisted.upper() in advertiser_name 
                            for whitelisted in advertiser_whitelist
                        )
                        
                        # #region agent log
                        # DEBUG: Whitelist matching
                        try:
                            import json
                            debug_log_path = '/app/debug.log'
                            whitelist_upper = [w.upper() for w in advertiser_whitelist]
                            matches = [w for w in whitelist_upper if w in advertiser_name]
                            
                            with open(debug_log_path, 'a') as f:
                                f.write(json.dumps({
                                    "timestamp": int(time.time() * 1000),
                                    "location": "tiktok_scraper.py:88",
                                    "message": "Whitelist check",
                                    "data": {
                                        "advertiser_name": ad.advertiser_name,
                                        "advertiser_name_upper": advertiser_name,
                                        "whitelist": advertiser_whitelist,
                                        "whitelist_upper": whitelist_upper,
                                        "matches": matches,
                                        "is_whitelisted": is_whitelisted
                                    },
                                    "sessionId": "debug-session",
                                    "hypothesisId": "C"
                                }) + '\n')
                        except Exception as log_e:
                            pass
                        # #endregion
                        
                        if not is_whitelisted:
                            logger.debug(f"Reklam whitelist nedeniyle filtrelendi: {ad.advertiser_name}")
                            filtered_count += 1
                            continue
                    
                    # DUPLICATE CHECK: Aynı içerikli reklamları engelle
                    ad_hash = self._compute_ad_hash(ad)
                    if ad_hash in self.seen_ad_hashes:
                        logger.debug(f"Reklam duplicate nedeniyle atlandı: {ad.advertiser_name}")
                        filtered_count += 1
                        
                        # #region agent log
                        try:
                            import json
                            with open('/app/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    "timestamp": int(time.time() * 1000),
                                    "location": "tiktok_scraper.py:122",
                                    "message": "Duplicate ad detected",
                                    "data": {
                                        "advertiser": ad.advertiser_name,
                                        "ad_text_preview": (ad.ad_text or "")[:50],
                                        "ad_hash": ad_hash
                                    },
                                    "sessionId": "debug-session",
                                    "runId": "test",
                                    "hypothesisId": "H5"
                                }) + '\n')
                        except: pass
                        # #endregion
                        
                        continue
                    
                    # Hash'i kaydet
                    self.seen_ad_hashes.add(ad_hash)
                    
                    # Filtrelerden geçti, ekle
                    self.scraped_ads.append(ad)
                    result.total_ads += 1
                    
                    if ad.is_banking_ad:
                        result.banking_ads += 1
                    
                    if ad.is_video():
                        result.video_ads += 1
                    elif ad.is_image():
                        result.image_ads += 1
                    else:
                        result.text_ads += 1
                    
                except Exception as e:
                    logger.error(f"Reklam işlenirken hata: {e}")
                    result.failed_ads += 1
                    result.add_error(f"Reklam işleme hatası: {str(e)}")
            
            if filtered_count > 0:
                logger.info(f"Filtre ile {filtered_count} reklam hariç tutuldu")
            logger.info(f"Scraping tamamlandı. Toplam: {result.total_ads}, Banking: {result.banking_ads}")
            
        except Exception as e:
            logger.error(f"Selenium scraping sırasında hata: {e}")
            result.add_error(f"Selenium scraping hatası: {str(e)}")
        
        result.complete()
        return result
    
    def _compute_ad_hash(self, ad: 'TikTokAd') -> str:
        """Reklam içeriğinden unique hash oluştur (duplicate detection için)"""
        import hashlib
        
        # Hash için kullanılacak alanlar
        advertiser = (ad.advertiser_name or "").strip().lower()
        text = (ad.ad_text or "").strip().lower()
        media = tuple(sorted(ad.media_urls)) if ad.media_urls else ()
        
        # Birleştir ve hash'le
        content = f"{advertiser}|{text}|{media}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _create_ad_from_selenium_data(self, ad_data: Dict) -> Optional[TikTokAd]:
        """Selenium verisinden TikTokAd objesi oluştur"""
        try:
            # Medya türünü belirle - RAW DATA'dan al
            media_type = MediaType.TEXT
            media_urls = ad_data.get('media_urls', [])

            # Önce raw_data'dan kontrol et
            raw_media_type = ad_data.get('raw_data', {}).get('media_type', '')
            if raw_media_type == 'video':
                media_type = MediaType.VIDEO
            elif raw_media_type == 'image':
                media_type = MediaType.IMAGE
            elif media_urls:  # URL varsa ama type yoksa, URL'den tahmin et
                first_url = media_urls[0].lower()
                if any(ext in first_url for ext in ['.mp4', '.mov', '.avi', 'video']):
                    media_type = MediaType.VIDEO
                elif any(ext in first_url for ext in ['.jpg', '.jpeg', '.png', '.gif', 'image']):
                    media_type = MediaType.IMAGE
                else:
                    # TikTok CDN URL'leri genelde video
                    media_type = MediaType.VIDEO
            
            # Ad text ve advertiser
            ad_text = clean_text(ad_data.get('ad_text', ''))
            advertiser_name = clean_text(ad_data.get('advertiser_name', 'Unknown Advertiser'))
            
            # Banking kontrolü
            is_banking, found_keywords = is_banking_related(
                f"{ad_text} {advertiser_name}", 
                settings.banking_keywords
            )
            
            ad = TikTokAd(
                ad_id=f"selenium_{ad_data.get('scrape_index', 'unknown')}_{int(time.time())}",
                advertiser_name=advertiser_name,
                ad_text=ad_text,
                media_type=media_type,
                media_urls=media_urls,
                is_banking_ad=is_banking,
                banking_keywords_found=found_keywords,
                scraped_at=datetime.now(),
                source_url=ad_data.get('ad_url', ''),
                raw_data=ad_data
            )
            
            logger.debug(f"Selenium ad oluşturuldu: {advertiser_name}")
            return ad
            
        except Exception as e:
            logger.error(f"Selenium ad objesi oluşturma hatası: {e}")
            return None
    
    def _get_mock_data(self) -> List[Dict]:
        """Mock veri döndür"""
        return [
            {
                'id': 'mock_ad_1',
                'advertiser': 'Garanti BBVA',
                'text': 'En uygun kredi faiz oranları burada! Hemen başvur. Garanti BBVA ile hayallerinizi gerçekleştirin.',
                'media_type': 'video',
                'media_url': 'https://example.com/video1.mp4',
                'created_time': '2025-09-01'
            },
            {
                'id': 'mock_ad_2', 
                'advertiser': 'İş Bankası',
                'text': 'Dijital bankacılık ile hayat daha kolay. Maximum kart avantajları. Online başvuru yapın.',
                'media_type': 'image',
                'media_url': 'https://example.com/image1.jpg',
                'created_time': '2025-09-02'
            },
            {
                'id': 'mock_ad_3',
                'advertiser': 'Yapı Kredi',
                'text': 'Kredi kartı kampanyaları! World kart ile dünyayı keşfedin. Puanlarınızı biriktirin.',
                'media_type': 'image',
                'media_url': 'https://example.com/image2.jpg',
                'created_time': '2025-09-03'
            },
            {
                'id': 'mock_ad_4',
                'advertiser': 'Papara',
                'text': 'Dijital cüzdan ile kolay ödeme! Papara Card ile her yerde alışveriş yapın.',
                'media_type': 'video',
                'media_url': 'https://example.com/video2.mp4',
                'created_time': '2025-08-30'
            }
        ]
    
    def _create_ad_object(self, ad_data: Dict) -> Optional[TikTokAd]:
        """Reklam verisinden TikTokAd objesi oluştur"""
        try:
            # Medya türünü belirle
            media_type = MediaType.TEXT
            if ad_data.get('media_type') == 'video':
                media_type = MediaType.VIDEO
            elif ad_data.get('media_type') == 'image':
                media_type = MediaType.IMAGE
            
            # Banking kontrolü
            ad_text = clean_text(ad_data.get('text', ''))
            advertiser_name = clean_text(ad_data.get('advertiser', ''))
            
            is_banking, found_keywords = is_banking_related(
                f"{ad_text} {advertiser_name}", 
                settings.banking_keywords
            )
            
            # TikTokAd objesi oluştur
            ad = TikTokAd(
                ad_id=ad_data.get('id', ''),
                advertiser_name=advertiser_name,
                ad_text=ad_text,
                media_type=media_type,
                media_urls=[ad_data.get('media_url')] if ad_data.get('media_url') else [],
                is_banking_ad=is_banking,
                banking_keywords_found=found_keywords,
                scraped_at=datetime.now(),
                source_url=ad_data.get('source_url'),
                raw_data=ad_data
            )
            
            logger.debug(f"Reklam oluşturuldu: {ad.ad_id} - {ad.advertiser_name}")
            return ad
            
        except Exception as e:
            logger.error(f"Reklam objesi oluşturulurken hata: {e}")
            return None
    
    def save_results(self, filepath: Optional[str] = None) -> str:
        """Sonuçları dosyaya kaydet"""
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"{settings.raw_data_path}\\tiktok_ads_{timestamp}.json"
        
        # Klasörü oluştur
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # JSON formatında kaydet
        ads_data = [ad.dict() for ad in self.scraped_ads]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(ads_data, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"Sonuçlar kaydedildi: {filepath}")
        return filepath
    
    def get_banking_ads(self) -> List[TikTokAd]:
        """Sadece bankacılık reklamlarını döndür"""
        return [ad for ad in self.scraped_ads if ad.is_banking_ad]
    
    def get_video_ads(self) -> List[TikTokAd]:
        """Sadece video reklamlarını döndür"""
        return [ad for ad in self.scraped_ads if ad.is_video()]