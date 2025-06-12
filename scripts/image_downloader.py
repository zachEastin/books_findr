"""
Book Image Downloader Module
Downloads book cover images from various sources
"""

import requests
import asyncio
import aiohttp
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import Optional, Dict, Any
import hashlib
import time
from urllib.parse import urlparse
import os

from .logger import scraper_logger
from .scraper import get_chrome_driver, clean_price, _initialize_chromedriver_once
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Configuration
BASE_DIR = Path(__file__).parent.parent
IMAGES_DIR = BASE_DIR / "static" / "images" / "books"
TIMEOUT = 15

# Ensure images directory exists
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def get_chrome_driver_with_images() -> webdriver.Chrome:
    """
    Create and configure Chrome WebDriver with images enabled specifically for image downloading.
    This ensures that images can be loaded when manually requested.
    """
    try:
        # Get the pre-initialized ChromeDriver path
        driver_path = _initialize_chromedriver_once()
        if not driver_path:
            raise Exception("ChromeDriver initialization failed")
        
        # Configure Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        # Explicitly ENABLE images for image downloading
        chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 1})
        
        # Additional options to avoid detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Create service using the pre-initialized ChromeDriver path
        service = Service(executable_path=driver_path)
        
        # Create the WebDriver instance
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(TIMEOUT)
        
        # Hide automation indicators
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        scraper_logger.info("Created Chrome driver with images enabled for image downloading")
        return driver
        
    except Exception as e:
        scraper_logger.error(f"Failed to create Chrome driver with images: {e}")
        raise


def get_image_filename(isbn: str, source: str) -> str:
    """Generate consistent image filename for ISBN and source"""
    # Create a hash of ISBN + source for uniqueness
    hash_obj = hashlib.md5(f"{isbn}_{source}".encode())
    return f"{isbn}_{source}_{hash_obj.hexdigest()[:8]}.jpg"


def get_image_path(isbn: str, source: str) -> Path:
    """Get full path for image file"""
    filename = get_image_filename(isbn, source)
    return IMAGES_DIR / filename


def image_exists(isbn: str, source: str) -> bool:
    """Check if image already exists for ISBN and source"""
    return get_image_path(isbn, source).exists()


async def download_image_from_url(url: str, isbn: str, source: str) -> Dict[str, Any]:
    """Download image from URL and save locally"""
    result = {
        "success": False,
        "isbn": isbn,
        "source": source,
        "image_path": None,
        "error": None
    }
    
    try:
        # Check if image already exists
        image_path = get_image_path(isbn, source)
        if image_path.exists():
            result.update({
                "success": True,
                "image_path": str(image_path.relative_to(BASE_DIR)),
                "error": "Image already exists"
            })
            return result
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as response:
                if response.status == 200:
                    content = await response.read()
                      # Validate it's an image
                    if len(content) > 1000 and (
                        content[:4] in [b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'\xff\xd8\xff\xfe'] or  # JPEG variants
                        content[:3] == b'\xff\xd8\xff' or  # JPEG
                        content[:8] == b'\x89PNG\r\n\x1a\n' or  # PNG
                        content[:6] in [b'GIF87a', b'GIF89a'] or  # GIF
                        content[:4] == b'RIFF' and content[8:12] == b'WEBP'  # WebP
                    ):
                        with open(image_path, 'wb') as f:
                            f.write(content)
                        
                        result.update({
                            "success": True,
                            "image_path": str(image_path.relative_to(BASE_DIR)),
                        })
                        scraper_logger.info(f"Downloaded image for {isbn} from {source}")
                    else:
                        result["error"] = "Invalid image format"
                else:
                    result["error"] = f"HTTP {response.status}"
                    
    except Exception as e:
        result["error"] = str(e)
        scraper_logger.error(f"Error downloading image for {isbn} from {source}: {e}")
    
    return result


def download_christianbook_image(isbn: str, url: str) -> Dict[str, Any]:
    """Download book image from ChristianBook"""
    result = {
        "success": False,
        "isbn": isbn,
        "source": "christianbook",
        "image_url": None,
        "image_path": None,
        "error": None
    }
    
    driver = None
    try:
        # Check if image already exists
        if image_exists(isbn, "christianbook"):
            image_path = get_image_path(isbn, "christianbook")
            result.update({
                "success": True,
                "image_path": str(image_path.relative_to(BASE_DIR)),
                "error": "Image already exists"
            })
            return result
        
        driver = get_chrome_driver_with_images()
        driver.get(url)
        
        # Wait for page to load
        wait = WebDriverWait(driver, TIMEOUT)
        
        # Look for the book image using multiple selectors
        image_selectors = [
            "div.CBD-ProductImage img",
            "div.CBD-ProductImageContainer img",
            "div[class*='ProductImage'] img",
            ".product-image img",
            "img[alt*='book']",
            "img[src*='product']"
        ]
        
        image_element = None
        for selector in image_selectors:
            try:
                image_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                break
            except TimeoutException:
                continue
        
        if image_element:
            image_url = image_element.get_attribute("src")
            if image_url and image_url.startswith("http"):
                result["image_url"] = image_url
                
                # Download the image
                download_result = asyncio.run(download_image_from_url(image_url, isbn, "christianbook"))
                result.update(download_result)
            else:
                result["error"] = "No valid image URL found"
        else:
            result["error"] = "No image element found"
            
    except Exception as e:
        result["error"] = str(e)
        scraper_logger.error(f"Error scraping ChristianBook image for {isbn}: {e}")
    finally:
        if driver:
            driver.quit()
    
    return result


def download_rainbowresource_image(isbn: str, url: str) -> Dict[str, Any]:
    """Download book image from RainbowResource (get lowest price item)"""
    result = {
        "success": False,
        "isbn": isbn,
        "source": "rainbowresource",
        "image_url": None,
        "image_path": None,
        "error": None
    }
    
    driver = None
    try:
        # Check if image already exists
        if image_exists(isbn, "rainbowresource"):
            image_path = get_image_path(isbn, "rainbowresource")
            result.update({
                "success": True,
                "image_path": str(image_path.relative_to(BASE_DIR)),
                "error": "Image already exists"
            })
            return result
        
        driver = get_chrome_driver_with_images()
        driver.get(url)
        
        # Wait for page to load
        wait = WebDriverWait(driver, TIMEOUT)
        
        # Look for search results with prices
        try:
            # Wait for search results to load
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".hawk-results__item")))
            
            # Find all result items with prices
            result_items = driver.find_elements(By.CSS_SELECTOR, ".hawk-results__item")
            
            lowest_price = float('inf')
            best_image_url = None
            
            for item in result_items:
                try:
                    # Get price
                    price_elem = item.find_element(By.CSS_SELECTOR, "span.special-price, .price")
                    price_text = price_elem.text.strip()
                    
                    # Extract numeric price
                    import re
                    price_match = re.search(r'\$?(\d+\.?\d*)', price_text)
                    if price_match:
                        price = float(price_match.group(1))
                        
                        # Get image for this item
                        img_elem = item.find_element(By.CSS_SELECTOR, "img")
                        img_url = img_elem.get_attribute("src")
                        
                        if price < lowest_price and img_url:
                            lowest_price = price
                            best_image_url = img_url
                            
                except Exception as e:
                    continue
            
            if best_image_url:
                result["image_url"] = best_image_url
                
                # Download the image
                download_result = asyncio.run(download_image_from_url(best_image_url, isbn, "rainbowresource"))
                result.update(download_result)
            else:
                result["error"] = "No image found for lowest price item"
                
        except TimeoutException:
            result["error"] = "Search results not found"
            
    except Exception as e:
        result["error"] = str(e)
        scraper_logger.error(f"Error scraping RainbowResource image for {isbn}: {e}")
    finally:
        if driver:
            driver.quit()
    
    return result


def download_abebooks_image(isbn: str, url: str) -> Dict[str, Any]:
    """Download book image from AbeBooks (lowest priced item)"""
    result = {
        "success": False,
        "isbn": isbn,
        "source": "abebooks",
        "image_url": None,
        "image_path": None,
        "error": None,
    }

    driver = None
    try:
        if image_exists(isbn, "abebooks"):
            image_path = get_image_path(isbn, "abebooks")
            result.update({
                "success": True,
                "image_path": str(image_path.relative_to(BASE_DIR)),
                "error": "Image already exists",
            })
            return result

        driver = get_chrome_driver_with_images()
        driver.get(url)

        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.result-data")))

        result_items = driver.find_elements(By.CSS_SELECTOR, "div.result-data")

        lowest_price = float("inf")
        best_image_url = None

        for item in result_items:
            try:
                price_elem = item.find_element(By.CSS_SELECTOR, "div.cf div.buy-box-data div.item-price-group p.item-price")
                price_text = price_elem.text.strip()
                price_value = clean_price(price_text)
                if price_value is None:
                    continue

                image_container = item.find_element(By.XPATH, "../div[contains(@class,'result-image')]//a/div[contains(@class,'srp-image-holder')]/img")
                img_url = image_container.get_attribute("src")

                if price_value < lowest_price and img_url:
                    lowest_price = price_value
                    best_image_url = img_url

            except Exception:
                continue

        if best_image_url:
            result["image_url"] = best_image_url
            download_result = asyncio.run(download_image_from_url(best_image_url, isbn, "abebooks"))
            result.update(download_result)
        else:
            result["error"] = "No image found for lowest price item"

    except Exception as e:
        result["error"] = str(e)
        scraper_logger.error(f"Error scraping AbeBooks image for {isbn}: {e}")
    finally:
        if driver:
            driver.quit()

    return result


def download_googlebooks_icon(isbn: str, url: str) -> Dict[str, Any]:
    """Download book thumbnail from Google Books API"""
    result = {
        "success": False,
        "isbn": isbn,
        "source": "googlebooks",
        "image_url": url,
        "image_path": None,
        "error": None
    }
    
    try:
        # Check if image already exists
        if image_exists(isbn, "googlebooks"):
            image_path = get_image_path(isbn, "googlebooks")
            result.update({
                "success": True,
                "image_path": str(image_path.relative_to(BASE_DIR)),
                "error": "Image already exists"
            })
            return result
        
        # Download the image directly
        download_result = asyncio.run(download_image_from_url(url, isbn, "googlebooks"))
        result.update(download_result)
        
    except Exception as e:
        result["error"] = str(e)
        scraper_logger.error(f"Error downloading Google Books icon for {isbn}: {e}")
    
    return result


def get_existing_image_info(isbn: str) -> Dict[str, Any]:
    """Get information about existing images for an ISBN"""
    sources = ["christianbook", "rainbowresource", "abebooks", "googlebooks"]
    images = {}
    
    for source in sources:
        image_path = get_image_path(isbn, source)
        if image_path.exists():
            # Get relative path for web serving
            relative_path = image_path.relative_to(BASE_DIR)
            images[source] = {
                "exists": True,
                "path": str(relative_path),
                "url": f"/{relative_path}".replace("\\", "/"),
                "size": image_path.stat().st_size
            }
        else:
            images[source] = {"exists": False}
    
    return images


def download_image_for_isbn_source(isbn: str, source: str, url: str) -> Dict[str, Any]:
    """Download image for specific ISBN and source"""
    if source.lower() == "christianbook":
        return download_christianbook_image(isbn, url)
    elif source.lower() == "rainbowresource":
        return download_rainbowresource_image(isbn, url)
    elif source.lower() == "abebooks":
        return download_abebooks_image(isbn, url)
    elif source.lower() == "googlebooks":
        return download_googlebooks_icon(isbn, url)
    else:
        return {
            "success": False,
            "isbn": isbn,
            "source": source,
            "error": f"Unsupported source: {source}"
        }


def cleanup_old_images(days_old: int = 30) -> Dict[str, Any]:
    """Clean up old image files"""
    result = {
        "success": True,
        "deleted_count": 0,
        "errors": []
    }
    
    try:
        cutoff_time = time.time() - (days_old * 24 * 60 * 60)
        
        for image_file in IMAGES_DIR.glob("*.jpg"):
            if image_file.stat().st_mtime < cutoff_time:
                try:
                    image_file.unlink()
                    result["deleted_count"] += 1
                    scraper_logger.info(f"Deleted old image: {image_file.name}")
                except Exception as e:
                    result["errors"].append(f"Failed to delete {image_file.name}: {e}")
                    
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        
    return result


def download_all_book_icons(books_data: dict) -> Dict[str, Any]:
    """
    Download all book icons from remote URLs to local storage
    
    Args:
        books_data: Dictionary of books data from books.json
        
    Returns:
        Dictionary with download statistics
    """
    result = {
        "success": True,
        "total_books": 0,
        "total_isbns": 0,
        "downloaded": 0,
        "already_local": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        # Iterate through all books
        for title, isbn_list in books_data.items():
            result["total_books"] += 1
            
            # Iterate through all ISBNs for this book
            for isbn_entry in isbn_list:
                for isbn, metadata in isbn_entry.items():
                    result["total_isbns"] += 1
                    
                    # Check if there's an icon URL to download
                    icon_url = metadata.get("icon_url", "")
                    if icon_url and not metadata.get("icon_path", ""):
                        try:
                            # Download the icon
                            scraper_logger.info(f"Downloading Google Books icon for ISBN {isbn}")
                            download_result = download_googlebooks_icon(isbn, icon_url)
                            
                            if download_result["success"]:
                                # Update metadata with local path
                                if download_result["error"] == "Image already exists":
                                    result["already_local"] += 1
                                else:
                                    result["downloaded"] += 1
                                
                                # Store the local path in the metadata
                                metadata["icon_path"] = download_result["image_path"]
                            else:
                                result["failed"] += 1
                                result["errors"].append(f"Failed to download icon for ISBN {isbn}: {download_result.get('error', 'Unknown error')}")
                        except Exception as e:
                            result["failed"] += 1
                            result["errors"].append(f"Error processing ISBN {isbn}: {str(e)}")
    
    except Exception as e:
        result["success"] = False
        result["errors"].append(f"Global error: {str(e)}")
    
    return result
