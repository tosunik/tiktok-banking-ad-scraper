#!/usr/bin/env python3
"""
FastAPI server for TikTok scraper - N8N integration
Windows compatible version
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn
from loguru import logger
import json
import sys
import os
from pathlib import Path
import traceback

# Add project paths - Railway compatible
current_dir = Path(__file__).parent
# Add current directory and src directory to path
sys.path.insert(0, str(current_dir))
if (current_dir / "src").exists():
    sys.path.insert(0, str(current_dir / "src"))

try:
    from src.scraper.tiktok_scraper import TikTokAdScraper
    from src.config.settings import settings
    logger.info("Successfully imported project modules")
    print("✅ Successfully imported project modules")
except ImportError as e:
    error_msg = f"Import error: {e}"
    logger.error(error_msg)
    logger.error("Make sure you're running from the project root directory")
    print(f"❌ {error_msg}")
    print(f"Current directory: {Path.cwd()}")
    print(f"Python path: {sys.path}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

app = FastAPI(
    title="TikTok Banking Ad Intelligence",
    description="N8N Integration for Turkish Banking Ad Analysis",
    version="1.0.0"
)

# CORS for N8N
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeRequest(BaseModel):
    keywords: List[str] = Field(default=["banka", "kredi", "garanti", "akbank"])
    max_results: int = Field(default=50, ge=1, le=200)
    region: str = Field(default="TR")
    days_back: int = Field(default=7, ge=1, le=30)
    banking_only: bool = Field(default=True)
    headless: bool = Field(default=True)

class N8NAdResponse(BaseModel):
    """N8N-friendly ad response format"""
    ad_id: str
    advertiser_name: str
    ad_text: str
    media_type: str
    media_urls: List[str]
    is_banking_ad: bool
    banking_keywords_found: List[str]
    scraped_at: str
    first_shown: Optional[str] = None
    last_shown: Optional[str] = None
    source_url: Optional[str] = None
    
    # N8N processing metadata
    n8n_meta: Dict[str, Any] = Field(default_factory=dict)

@app.get("/")
async def root():
    return {
        "message": "TikTok Banking Ad Intelligence API", 
        "status": "running",
        "endpoints": ["/health", "/scrape-tiktok", "/test-scrape", "/turkish-banks"]
    }

@app.get("/test-selenium")
async def test_selenium():
    try:
        from src.scraper.tiktok_selenium_scraper import TikTokSeleniumScraper
        scraper = TikTokSeleniumScraper(headless=True)
        success = scraper.setup_driver()
        if success:
            scraper.close_driver()
        return {"selenium_works": success, "chrome_installed": True}
    except Exception as e:
        return {"selenium_works": False, "error": str(e), "chrome_installed": False}

@app.get("/health")
async def health_check():
    """Health check for N8N monitoring"""
    try:
        # Test basic imports
        from src.config.settings import settings
        return {
            "status": "healthy",
            "service": "TikTok Banking Ad Scraper",
            "version": "1.0.0",
            "settings_loaded": True,
            "banking_keywords_count": len(settings.banking_keywords)
        }
    except Exception as e:
        import traceback
        error_detail = {
            "status": "unhealthy",
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
        logger.error(f"Health check failed: {error_detail}")
        return error_detail

@app.post("/scrape-tiktok")
async def scrape_tiktok_ads(request: ScrapeRequest):
    """
    Main scraping endpoint for N8N
    Returns N8N-compatible format: array of ad objects
    """
    logger.info(f"N8N scraping request: keywords={request.keywords}, max={request.max_results}")
    
    try:
        # Initialize scraper
        scraper = TikTokAdScraper(headless=request.headless)
        
        # Execute scraping
        logger.info(f"Scraping başlatılıyor: {request.max_results} maksimum reklam")
        result = scraper.search_ads(
            keywords=request.keywords,
            max_results=request.max_results
        )
        
        # Convert to N8N format - RETURN ARRAY FOR N8N
        n8n_ads = []
        
        for ad in scraper.scraped_ads:
            # Filter banking ads if requested
            if request.banking_only and not ad.is_banking_ad:
                continue
            
            # Create N8N item
            n8n_ad = {
                "ad_id": ad.ad_id,
                "advertiser_name": ad.advertiser_name or "Unknown",
                "ad_text": ad.ad_text or "",
                "media_type": ad.media_type.value,
                "media_urls": ad.media_urls or [],
                "is_banking_ad": ad.is_banking_ad,
                "banking_keywords_found": ad.banking_keywords_found,
                "scraped_at": ad.scraped_at.isoformat(),
                "first_shown": ad.raw_data.get('first_shown'),
                "last_shown": ad.raw_data.get('last_shown'),
                "source_url": ad.source_url,
                
                # N8N specific metadata
                "n8n_meta": {
                    "media_count": len(ad.media_urls),
                    "has_video": ad.is_video(),
                    "has_image": ad.is_image(),
                    "is_banking": ad.is_banking_ad,
                    "processing_priority": "high" if ad.is_banking_ad else "normal",
                    "advertiser_slug": (ad.advertiser_name or "unknown").lower().replace(' ', '_'),
                    "keywords_count": len(ad.banking_keywords_found),
                    "video_url": ad.media_urls[0] if ad.media_urls and ad.is_video() else None,
                    "image_url": ad.media_urls[0] if ad.media_urls and ad.is_image() else None,
                    "banking_score": len(ad.banking_keywords_found) * 10,
                    "content_length": len(ad.ad_text) if ad.ad_text else 0
                },
                
                # Summary for N8N (added to each item)
                "scrape_summary": {
                    "total_ads": result.total_ads,
                    "banking_ads": result.banking_ads,
                    "video_ads": result.video_ads,
                    "image_ads": result.image_ads,
                    "duration_seconds": result.duration_seconds or 0.0
                }
            }
            n8n_ads.append(n8n_ad)
        
        logger.info(f"N8N response ready: {len(n8n_ads)} ads")
        
        # Return array directly for N8N
        return n8n_ads
        
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "type": type(e).__name__,
                "success": False
            }
        )

@app.get("/turkish-banks")
async def get_turkish_banks():
    """Get Turkish banks list for N8N dropdown"""
    return {
        "all_banks": settings.turkish_banks,
        "major_banks": ["garanti", "isbank", "yapikredi", "akbank", "halkbank", "vakifbank"],
        "digital_fintech": ["papara", "ininal", "tosla", "denizbank", "ingbank"]
    }

@app.get("/test-scrape")
async def test_scrape():
    """Quick test endpoint for debugging"""
    try:
        scraper = TikTokAdScraper(headless=True)
        result = scraper.search_ads(keywords=["garanti"], max_results=3)
        
        return {
            "test_successful": True,
            "ads_found": result.total_ads,
            "banking_ads": result.banking_ads,
            "duration": result.duration_seconds,
            "sample_ad": scraper.scraped_ads[0].dict() if scraper.scraped_ads else None,
            "errors": result.errors
        }
    except Exception as e:
        return {
            "test_successful": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

if __name__ == "__main__":
    # Setup logging - ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    logger.add("logs/fastapi.log", rotation="1 day", retention="30 days")
    
    # Print startup info to stdout (Railway logs)
    print("=" * 50)
    print("Starting TikTok Banking Intelligence FastAPI server...")
    print(f"Current directory: {Path.cwd()}")
    print(f"Python path: {sys.path}")
    print("=" * 50)
    
    # Get port from environment (Railway sets PORT)
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting TikTok Banking Intelligence FastAPI server on port {port}...")
    print(f"Starting server on port {port}...")
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.error(traceback.format_exc())
        print(f"ERROR: Failed to start server: {e}")
        print(traceback.format_exc())
        raise
