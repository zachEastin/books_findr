"""
Book Price Tracker - Async Web Scraping Module
Handles scraping from AbeBooks, Christianbook, and RainbowResource
Uses asyncio for concurrent scraping to improve performance
Integrates with ISBNdb API for enhanced search capabilities
"""

import time
import asyncio
import urllib.parse
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import pandas as pd
from pathlib import Path
from datetime import datetime
import re  # for clean_price
from typing import Optional
import os
import stat
import subprocess
import threading

from .logger import scraper_logger, log_scrape_result, log_task_start, log_task_complete
import json


# Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PRICES_CSV = DATA_DIR / "prices.csv"
TIMEOUT = 15  # seconds
MAX_CONCURRENT_SCRAPERS = 3  # Limit concurrent scrapers to be respectful

# Shared thread pool for running blocking Selenium calls
executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SCRAPERS)

# Global ChromeDriver management - initialize once and reuse throughout session
_chromedriver_path = None
_chromedriver_lock = threading.Lock()
_chromedriver_initialized = False


def _fix_chromedriver_permissions_windows(driver_path: str) -> bool:
    """
    Fix ChromeDriver permissions on Windows using PowerShell.
    This ensures the downloaded ChromeDriver executable has proper execute permissions.
    
    Args:
        driver_path: Path to the ChromeDriver executable
        
    Returns:
        bool: True if permissions were set successfully, False otherwise
    """
    try:
        # Check if file is already executable (has correct permissions)
        if os.access(driver_path, os.X_OK):
            scraper_logger.info(f"ChromeDriver already has execute permissions: {driver_path}")
            return True
            
        scraper_logger.info(f"Attempting to fix ChromeDriver permissions on Windows: {driver_path}")
        
        # Use PowerShell to set full control permissions for the current user
        powershell_cmd = [
            "powershell", "-Command",
            f'$acl = Get-Acl "{driver_path}"; '
            f'$accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule("{os.environ.get("USERNAME", "")}", "FullControl", "Allow"); '
            f'$acl.SetAccessRule($accessRule); '
            f'Set-Acl "{driver_path}" $acl'
        ]
        
        result = subprocess.run(powershell_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # Verify the fix worked
            if os.access(driver_path, os.X_OK):
                scraper_logger.info("Successfully fixed ChromeDriver permissions using PowerShell")
                return True
            else:
                scraper_logger.warning("PowerShell command succeeded but file still not executable")
                
        else:
            scraper_logger.error(f"PowerShell permission fix failed: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        scraper_logger.error("PowerShell permission fix timed out")
    except Exception as e:
        scraper_logger.error(f"Error fixing ChromeDriver permissions: {e}")
    
    # Fallback: Try using os.chmod (may not work on Windows but worth trying)
    try:
        os.chmod(driver_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        scraper_logger.info("Applied fallback permissions using os.chmod")
        return os.access(driver_path, os.X_OK)
    except Exception as e:
        scraper_logger.error(f"Fallback permission fix failed: {e}")
        
    return False


def _initialize_chromedriver_once() -> Optional[str]:
    """
    Initialize ChromeDriver once per session and return the path to the executable.
    This function is thread-safe and will only download/initialize once per session,
    then reuse the same executable for all browser launches.
    
    Returns:
        str: Path to the ChromeDriver executable, or None if initialization failed
    """
    global _chromedriver_path, _chromedriver_initialized
    
    with _chromedriver_lock:
        # If already initialized, return the cached path
        if _chromedriver_initialized and _chromedriver_path:
            if os.path.exists(_chromedriver_path) and os.access(_chromedriver_path, os.X_OK):
                return _chromedriver_path
            else:
                scraper_logger.warning("Cached ChromeDriver path is invalid, reinitializing...")
                _chromedriver_initialized = False
                _chromedriver_path = None
        
        if _chromedriver_initialized:
            return _chromedriver_path
            
        scraper_logger.info("Initializing ChromeDriver (one-time setup for session)...")
        
        try:
            # Download and get the ChromeDriver path
            # webdriver-manager handles caching, so subsequent calls are fast
            driver_path = ChromeDriverManager().install()
            scraper_logger.info(f"ChromeDriver downloaded/located at: {driver_path}")
            
            # Verify the file exists
            if not os.path.exists(driver_path):
                scraper_logger.error(f"ChromeDriver file not found after download: {driver_path}")
                return None
            
            # Check and fix permissions on Windows
            if os.name == 'nt':  # Windows
                if not os.access(driver_path, os.X_OK):
                    scraper_logger.warning("ChromeDriver lacks execute permissions, attempting to fix...")
                    if not _fix_chromedriver_permissions_windows(driver_path):
                        scraper_logger.error("Failed to fix ChromeDriver permissions")
                        return None
                else:
                    scraper_logger.info("ChromeDriver permissions are correct")
            
            # Test the ChromeDriver by creating a minimal service
            try:
                # Don't start the service, just verify it can be created
                Service(driver_path)
                scraper_logger.info("ChromeDriver validation successful")
            except Exception as e:
                scraper_logger.error(f"ChromeDriver validation failed: {e}")
                return None
            
            # Cache the successful path
            _chromedriver_path = driver_path
            _chromedriver_initialized = True
            
            scraper_logger.info(f"ChromeDriver session initialization complete: {driver_path}")
            return driver_path
            
        except Exception as e:
            scraper_logger.error(f"Failed to initialize ChromeDriver: {e}")
            _chromedriver_initialized = True  # Mark as attempted to avoid repeated failures
            _chromedriver_path = None
            return None


def get_chrome_driver() -> webdriver.Chrome:
    """
    Create and configure Chrome WebDriver using the pre-initialized ChromeDriver executable.
    This function reuses the same ChromeDriver executable that was downloaded once at session start.
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
        # Disable image loading to improve performance and prevent automatic image scraping
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
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
        
        scraper_logger.debug(f"Created Chrome WebDriver instance using: {driver_path}")
        return driver
        
    except Exception as e:
        scraper_logger.error(f"Failed to create Chrome driver: {e}")
        raise


def initialize_chromedriver_session() -> bool:
    """
    Initialize ChromeDriver for the current session.
    Call this once at the start of your scraping session for optimal performance.
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        driver_path = _initialize_chromedriver_once()
        if driver_path:
            scraper_logger.info(f"ChromeDriver session ready: {driver_path}")
            return True
        else:
            scraper_logger.error("ChromeDriver session initialization failed")
            return False
    except Exception as e:
        scraper_logger.error(f"Error initializing ChromeDriver session: {e}")
        return False


def clean_price(price_text: str) -> Optional[float]:
    """Extract numeric price from text"""
    if not price_text:
        return None

    # Remove common currency symbols and text
    # Remove all non-digit and non-period characters, then ensure only one period (decimal point) remains and it's surrounded by digits
    cleaned = re.sub(r'^\.+|\.+$', '', re.sub(r"[^\d.]", "", price_text))
    # Ensure the period is surrounded by digits (e.g., ".99" -> "0.99", "99." -> "99.0")
    if cleaned.startswith('.'):
        cleaned = '0' + cleaned
    if cleaned.endswith('.'):
        cleaned = cleaned + '0'

    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def get_search_strategies(isbn_data: dict) -> list[tuple[str, str]]:
    """
    Get search strategies for an ISBN in order of preference

    Args:
        isbn: The original ISBN metadata dictionary

    Returns:
        List of (search_term, strategy_name) tuples in order of preference
    """
    strategies = []

    try:
        # Strategy 1: Use ISBN-13 if available
        isbn_13 = isbn_data.get("isbn13")
        if isbn_13:
            strategies.append((isbn_13, "ISBN-13 from metadata"))
            scraper_logger.info(f"Found ISBN-13 {isbn_13}")

        # Strategy 2: Use title if available
        title = isbn_data.get("title")
        if title:
            # Clean title for search (remove subtitle after colon, etc.)
            clean_title = title.split(":")[0].strip()
            strategies.append((clean_title, "title from metadata"))
            scraper_logger.info(f"Found title '{clean_title}' for {isbn_data.get('isbn_13', 'unknown')}")
        else:
            scraper_logger.warning(f"No title found in metadata for ISBN {isbn_data.get('isbn_13', 'unknown')}")

    except Exception as e:
        scraper_logger.warning(f"Error getting search strategies for {isbn_data.get('isbn_13', 'unknown')}: {e}")

    return strategies


def _scrape_christianbook_sync(search_term: str, search_url: str) -> dict:
    """Synchronous helper function for Christianbook scraping"""
    result_update = {
        "price": None,
        "title": None,
        "url": search_url,
        "notes": "",
        "success": False,
    }

    driver = None
    try:
        driver = get_chrome_driver()
        scraper_logger.info(f"Scraping Christianbook for term: {search_term}")

        driver.get(search_url)

        # Wait for search results
        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Wait 5 seconds for dynamic content to load
        time.sleep(5)

        # Look for the first search result
        try:
            # Find product title
            title_selectors = [".CB-ProductListItem-Title"]

            title_element = None
            for selector in title_selectors:
                try:
                    title_element = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if title_element:
                result_update["title"] = title_element.text.strip()
                # Update URL to specific product page
                href = title_element.get_attribute("href")
                if href:
                    result_update["url"] = href

            # Find price
            price_selectors = [
                ".price .sale-price",
                ".price .our-price",
                ".CBD-ProductDetailActionPrice",
                ".CBD-ProductDetailActionPrice span .sr-only",
                ".sale-price",
                ".our-price",
                "[class*='price']",
            ]

            price_element = None
            for selector in price_selectors:
                try:
                    price_element = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if price_element:
                price_text = price_element.text.strip()
                price_value = clean_price(price_text)
                if price_value and price_value > 0:
                    result_update["price"] = price_value
                    result_update["success"] = True
                    result_update["notes"] = "Found price in search results"
                else:
                    result_update["notes"] = f"Invalid price format: {price_text}"
            else:
                result_update["notes"] = "No price element found"

        except NoSuchElementException:
            result_update["notes"] = "No search results found"

    except TimeoutException:
        result_update["notes"] = "Page load timeout"
        scraper_logger.error(f"Timeout scraping Christianbook for term {search_term}")
    except WebDriverException as e:
        result_update["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping Christianbook for term {search_term}: {e}")
    except Exception as e:
        result_update["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping Christianbook for term {search_term}: {e}")
    finally:
        if driver:
            driver.quit()

    return result_update


def _scrape_rainbowresource_sync(search_term: str, search_url: str) -> dict:
    """Synchronous helper function for RainbowResource scraping"""
    result_update = {
        "price": None,
        "title": None,
        "url": search_url,
        "notes": "",
        "success": False,
    }

    driver = None
    try:
        driver = get_chrome_driver()
        scraper_logger.info(f"Scraping RainbowResource for term: {search_term}")

        driver.get(search_url)

        # Wait for search results
        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Wait 5 seconds for dynamic content to load
        time.sleep(5)

        # Look for search results
        try:
            # Find product title
            title_selectors = [".hawk-results__item-name"]

            title_element = None
            for selector in title_selectors:
                try:
                    title_element = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if title_element:
                result_update["title"] = title_element.text.strip()
                # Update URL to specific product page if available
                href = title_element.get_attribute("href")
                if href:
                    result_update["url"] = href

            # Find price
            price_selectors = [".special-price", "[class*='price']"]

            price_element = None
            for selector in price_selectors:
                try:
                    price_element = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if price_element:
                price_text = price_element.text.strip()
                price_value = clean_price(price_text)
                if price_value and price_value > 0:
                    result_update["price"] = price_value
                    result_update["success"] = True
                    result_update["notes"] = "Found price in search results"
                else:
                    result_update["notes"] = f"Invalid price format: {price_text}"
            else:
                result_update["notes"] = "No price element found"

        except NoSuchElementException:
            result_update["notes"] = "No search results found"

    except TimeoutException:
        result_update["notes"] = "Page load timeout"
        scraper_logger.error(f"Timeout scraping RainbowResource for term {search_term}")
    except WebDriverException as e:
        result_update["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping RainbowResource for term {search_term}: {e}")
    except Exception as e:
        result_update["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping RainbowResource for term {search_term}: {e}")
    finally:
        if driver:
            driver.quit()

    return result_update


def _scrape_abebooks_sync(search_term: str, search_url: str) -> dict:
    """Synchronous helper function for AbeBooks scraping"""
    result_update = {
        "price": None,
        "title": None,
        "url": search_url,
        "notes": "",
        "success": False,
    }

    driver = None
    try:
        driver = get_chrome_driver()
        scraper_logger.info(f"Scraping AbeBooks for term: {search_term}")

        driver.get(search_url)

        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)

        result_items = driver.find_elements(By.CSS_SELECTOR, "div.result-data")

        lowest_price = float("inf")
        best_title = None
        best_url = None

        for item in result_items:
            try:
                price_elem = item.find_element(By.CSS_SELECTOR, "div.cf div.buy-box-data div.item-price-group p.item-price")
                price_text = price_elem.text.strip()
                price_value = clean_price(price_text)
                if not price_value or price_value <= 0:
                    continue

                # Get Shipping and add to Price
                shipping_elem = item.find_element(By.CSS_SELECTOR, "div.cf div.buy-box-data div.item-price-group span")
                shipping_text = shipping_elem.text.strip()
                shipping_value = clean_price(shipping_text)
                if shipping_value and shipping_value > 0:
                    price_value += shipping_value

                title_elem = item.find_element(By.CSS_SELECTOR, "div.cf div.result-detail h2.title a span")
                title_text = title_elem.text.strip()
                url_elem = item.find_element(By.CSS_SELECTOR, "div.cf div.result-detail h2.title a")
                href = url_elem.get_attribute("href")

                if price_value < lowest_price:
                    lowest_price = price_value
                    best_title = title_text
                    best_url = href

            except NoSuchElementException:
                continue

        if lowest_price != float("inf"):
            result_update.update({
                "price": lowest_price,
                "title": best_title,
                "url": best_url or search_url,
                "success": True,
                "notes": "Found price in search results",
            })
        else:
            result_update["notes"] = "No valid prices found"

    except TimeoutException:
        result_update["notes"] = "Page load timeout"
        scraper_logger.error(f"Timeout scraping AbeBooks for term {search_term}")
    except WebDriverException as e:
        result_update["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping AbeBooks for term {search_term}: {e}")
    except Exception as e:
        result_update["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping AbeBooks for term {search_term}: {e}")
    finally:
        if driver:
            driver.quit()

    return result_update


def _scrape_camelcamelcamel_sync(isbn: str, search_url: str) -> dict:
    """Synchronous helper function for CamelCamelCamel scraping"""
    result_update = {
        "price": None,
        "title": None,
        "url": search_url,
        "notes": "",
        "success": False,
    }

    driver = None
    try:
        driver = get_chrome_driver()
        scraper_logger.info(f"Scraping CamelCamelCamel for ISBN: {isbn}")

        driver.get(search_url)

        # Wait for search results
        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Look for search results
        try:
            # Find first search result
            search_results = driver.find_elements(By.CSS_SELECTOR, ".search_item, .product")

            if search_results:
                first_result = search_results[0]

                # Get title
                try:
                    title_element = first_result.find_element(By.CSS_SELECTOR, "a")
                    result_update["title"] = title_element.text.strip()
                    href = title_element.get_attribute("href")
                    if href:
                        result_update["url"] = href
                except NoSuchElementException:
                    pass

                # Get current Amazon price
                try:
                    price_element = first_result.find_element(
                        By.CSS_SELECTOR, ".price, .amazon_price, [class*='price']"
                    )
                    price_text = price_element.text.strip()
                    price_value = clean_price(price_text)
                    if price_value and price_value > 0:
                        result_update["price"] = price_value
                        result_update["success"] = True
                        result_update["notes"] = "Current Amazon price from CamelCamelCamel"
                    else:
                        result_update["notes"] = f"Invalid price format: {price_text}"
                except NoSuchElementException:
                    result_update["notes"] = "No price found in search result"
            else:
                result_update["notes"] = "No search results found"

        except NoSuchElementException:
            result_update["notes"] = "No search results container found"

    except TimeoutException:
        result_update["notes"] = "Page load timeout"
        scraper_logger.error(f"Timeout scraping CamelCamelCamel for ISBN {isbn}")
    except WebDriverException as e:
        result_update["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping CamelCamelCamel for ISBN {isbn}: {e}")
    except Exception as e:
        result_update["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping CamelCamelCamel for ISBN {isbn}: {e}")
    finally:
        if driver:
            driver.quit()

    return result_update


async def scrape_christianbook_async(isbn_data: dict, book_title: str = "") -> dict:
    """
    Async scrape book price from Christianbook.com with enhanced search strategies

    Args:
        isbn: The ISBN metadata to search for

    Returns:
        dictionary with scraping results
    """
    result = {
        "isbn": isbn_data.get("isbn13", "unknown"),
        "book_title": book_title,
        "source": "Christianbook",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    try:
        # Get search strategies in order of preference
        search_strategies = get_search_strategies(isbn_data)
        scraper_logger.info(
            f"Christianbook: Trying {len(search_strategies)} search strategies for {isbn_data.get('title', 'unknown')}"
        )

        # Try each search strategy until we find results
        for search_term, strategy_name in search_strategies:
            try:  # Christianbook search URL with URL encoding
                encoded_term = urllib.parse.quote(search_term)
                search_url = f"https://www.christianbook.com/apps/search?Ntt={encoded_term}&Ntk=keywords&action=Search&Ne=0&event=BRSRCG%7CPSEN&nav_search=1&cms=1&ps_exit=RETURN%7Clegacy&ps_domain=www"
                result["url"] = search_url

                scraper_logger.info(f"Christianbook: Trying {strategy_name} with term '{search_term}'")

                loop = asyncio.get_running_loop()
                scraping_result = await loop.run_in_executor(
                    executor, _scrape_christianbook_sync, search_term, search_url
                )

                if scraping_result.get("success"):
                    result.update(scraping_result)
                    result["notes"] = f"Found using {strategy_name}: {result['notes']}"
                    scraper_logger.info(f"Christianbook: Success with {strategy_name}")
                    break
                else:
                    scraper_logger.info(
                        f"Christianbook: No results with {strategy_name} for term {search_term} and url {search_url}"
                    )

            except Exception as e:
                scraper_logger.warning(f"Christianbook: Error with {strategy_name}: {e}")
                continue

        if not result["success"]:
            result["notes"] = f"No results found with any search strategy (tried {len(search_strategies)} methods)"

    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(
            f"Unexpected error scraping Christianbook for ISBN {isbn_data.get('isbn13', 'unknown')}: {e}"
        )

    log_scrape_result(
        scraper_logger,
        isbn_data.get("isbn13", "unknown"),
        "Christianbook",
        result["success"],
        result["price"],
        result["notes"],
    )
    return result


async def scrape_rainbowresource_async(isbn_data: dict, book_title: str = "") -> dict:
    """
    Async scrape book price from RainbowResource.com with enhanced search strategies

    Args:
        isbn: The ISBN metadata to search for

    Returns:
        dictionary with scraping results
    """
    result = {
        "isbn": isbn_data.get("isbn13", "unknown"),
        "book_title": book_title,
        "source": "RainbowResource",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    try:
        # Get search strategies in order of preference
        search_strategies = get_search_strategies(isbn_data)
        scraper_logger.info(
            f"RainbowResource: Trying {len(search_strategies)} search strategies for {isbn_data.get('title', 'unknown')}"
        )

        # Try each search strategy until we find results
        for search_term, strategy_name in search_strategies:
            try:  # RainbowResource search URL with URL encoding
                encoded_term = urllib.parse.quote(search_term)
                search_url = f"https://www.rainbowresource.com/catalogsearch/result?q={encoded_term}"
                result["url"] = search_url

                scraper_logger.info(f"RainbowResource: Trying {strategy_name} with term '{search_term}'")

                loop = asyncio.get_running_loop()
                scraping_result = await loop.run_in_executor(
                    executor, _scrape_rainbowresource_sync, search_term, search_url
                )

                if scraping_result.get("success"):
                    result.update(scraping_result)
                    result["notes"] = f"Found using {strategy_name}: {result['notes']}"
                    scraper_logger.info(f"RainbowResource: Success with {strategy_name}")
                    break
                else:
                    scraper_logger.info(
                        f"RainbowResource: No results with {strategy_name} for term {search_term} and url {search_url}"
                    )

            except Exception as e:
                scraper_logger.warning(f"RainbowResource: Error with {strategy_name}: {e}")
                continue

        if not result["success"]:
            result["notes"] = f"No results found with any search strategy (tried {len(search_strategies)} methods)"

    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(
            f"Unexpected error scraping RainbowResource for ISBN {isbn_data.get('isbn13', 'unknown')}: {e}"
        )

    log_scrape_result(
        scraper_logger,
        isbn_data.get("isbn13", "unknown"),
        "RainbowResource",
        result["success"],
        result["price"],
        result["notes"],
    )
    return result


async def scrape_abebooks_async(isbn_data: dict, book_title: str = "") -> dict:
    """Async scrape book price from AbeBooks with enhanced search strategies"""
    result = {
        "isbn": isbn_data.get("isbn13", "unknown"),
        "book_title": book_title,
        "source": "AbeBooks",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    try:
        search_strategies = get_search_strategies(isbn_data)
        scraper_logger.info(
            f"AbeBooks: Trying {len(search_strategies)} search strategies for {isbn_data.get('title', 'unknown')}"
        )

        for search_term, strategy_name in search_strategies:
            try:
                encoded_term = urllib.parse.quote(search_term)
                search_url = f"https://www.abebooks.com/servlet/SearchResults?kn={encoded_term}"
                result["url"] = search_url

                scraper_logger.info(f"AbeBooks: Trying {strategy_name} with term '{search_term}'")

                loop = asyncio.get_running_loop()
                scraping_result = await loop.run_in_executor(
                    executor, _scrape_abebooks_sync, search_term, search_url
                )

                if scraping_result.get("success"):
                    result.update(scraping_result)
                    result["notes"] = f"Found using {strategy_name}: {result['notes']}"
                    scraper_logger.info(f"AbeBooks: Success with {strategy_name}")
                    break
                else:
                    scraper_logger.info(
                        f"AbeBooks: No results with {strategy_name} for term {search_term} and url {search_url}"
                    )

            except Exception as e:
                scraper_logger.warning(f"AbeBooks: Error with {strategy_name}: {e}")
                continue

        if not result["success"]:
            result["notes"] = f"No results found with any search strategy (tried {len(search_strategies)} methods)"

    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(
            f"Unexpected error scraping AbeBooks for ISBN {isbn_data.get('isbn13', 'unknown')}: {e}"
        )

    log_scrape_result(
        scraper_logger,
        isbn_data.get("isbn13", "unknown"),
        "AbeBooks",
        result["success"],
        result["price"],
        result["notes"],
    )
    return result


async def scrape_camelcamelcamel_async(isbn_data: dict, book_title: str = "") -> dict:
    """
    Async scrape Amazon price history from CamelCamelCamel with enhanced search strategies
    Note: This gets the current Amazon price, not historical data

    Args:
        isbn: The ISBN metadata to search for

    Returns:
        dictionary with scraping results
    """
    result = {
        "isbn": isbn_data.get("isbn13", "unknown"),
        "book_title": book_title,
        "source": "CamelCamelCamel",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    try:
        # Get search strategies in order of preference
        search_strategies = get_search_strategies(isbn_data)
        scraper_logger.info(
            f"CamelCamelCamel: Trying {len(search_strategies)} search strategies for {isbn_data.get('title', 'unknown')}"
        )

        # Try each search strategy until we find results
        for search_term, strategy_name in search_strategies:
            try:  # CamelCamelCamel search URL with URL encoding
                encoded_term = urllib.parse.quote(search_term)
                search_url = f"https://camelcamelcamel.com/search?sq={encoded_term}"
                result["url"] = search_url

                scraper_logger.info(f"CamelCamelCamel: Trying {strategy_name} with term '{search_term}'")

                loop = asyncio.get_running_loop()
                scraping_result = await loop.run_in_executor(
                    executor, _scrape_camelcamelcamel_sync, search_term, search_url
                )

                if scraping_result.get("success"):
                    result.update(scraping_result)
                    result["notes"] = f"Found using {strategy_name}: {result['notes']}"
                    scraper_logger.info(f"CamelCamelCamel: Success with {strategy_name}")
                    break
                else:
                    scraper_logger.info(
                        f"CamelCamelCamel: No results with {strategy_name} for term {search_term} and url {search_url}"
                    )

            except Exception as e:
                scraper_logger.warning(f"CamelCamelCamel: Error with {strategy_name}: {e}")
                continue

        if not result["success"]:
            result["notes"] = f"No results found with any search strategy (tried {len(search_strategies)} methods)"

    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(
            f"Unexpected error scraping CamelCamelCamel for ISBN {isbn_data.get('isbn13', 'unknown')}: {e}"
        )

    log_scrape_result(
        scraper_logger,
        isbn_data.get("isbn13", "unknown"),
        "CamelCamelCamel",
        result["success"],
        result["price"],
        result["notes"],
    )
    return result


async def scrape_all_sources_async(isbn: dict, book_title: str = "") -> list[dict]:
    """
    Async scrape an ISBN from all sources concurrently

    Args:
        isbn: The ISBN to scrape

    Returns:
        List of result dictionaries from all sources
    """
    log_task_start(
        scraper_logger,
        f"Async scraping all sources for ISBN {isbn.get('isbn13') or 'unknown'}",
    )
    start_time = time.time()  # Create async tasks for all scrapers
    tasks = [
        scrape_christianbook_async(isbn, book_title),
        scrape_rainbowresource_async(isbn, book_title),
        scrape_abebooks_async(isbn, book_title),
    ]

    try:
        # Run all scrapers concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle any exceptions
        processed_results = []
        source_names = ["Christianbook", "RainbowResource", "AbeBooks"]  # , "CamelCamelCamel"]

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle exceptions from failed scrapers
                scraper_logger.error(f"Error in {source_names[i]} for ISBN {isbn}: {result}")
                processed_results.append(
                    {
                        "isbn": isbn.get("isbn13", "unknown"),
                        "book_title": book_title,
                        "source": source_names[i],
                        "price": None,
                        "title": None,
                        "url": None,
                        "notes": f"Scraper function failed: {str(result)}",
                        "success": False,
                    }
                )
            else:
                processed_results.append(result)

        results = processed_results

    except Exception as e:
        scraper_logger.error(f"Unexpected error in scrape_all_sources for ISBN {isbn}: {e}")
        results = []

    end_time = time.time()
    duration = end_time - start_time

    successful_scrapes = len([r for r in results if r.get("success", False)])
    log_task_complete(
        scraper_logger, f"Async scraping all sources for ISBN {isbn.get('isbn13') or 'unknown'}", duration
    )
    scraper_logger.info(
        f"Completed async scraping ISBN {isbn.get('isbn13')}: {successful_scrapes}/{len(tasks)} sources successful"
    )

    return results


async def scrape_multiple_isbns(
    isbns: list[tuple[str, str, dict]], batch_size: int = MAX_CONCURRENT_SCRAPERS
) -> list[dict]:
    """
    Async scrape multiple ISBNs with controlled concurrency

    Args:
        isbns: List of ISBNs to scrape
        batch_size: Maximum number of concurrent ISBN scraping operations

    Returns:
        List of all scraping results
    """
    log_task_start(
        scraper_logger, f"Starting async bulk scraping for {len(isbns)} ISBNs"
    )
    start_time = time.time()
    
    # Ensure ChromeDriver session is initialized for batch processing
    if not _chromedriver_initialized:
        scraper_logger.info("Initializing ChromeDriver session for batch processing...")
        if not initialize_chromedriver_session():
            scraper_logger.error("Failed to initialize ChromeDriver session for batch processing")
            return []

    all_results = []

    # Process ISBNs in batches to avoid overwhelming the sites
    for i in range(0, len(isbns), batch_size):
        batch = isbns[i : i + batch_size]
        scraper_logger.info(f"Processing batch {i // batch_size + 1}: ISBNs {i + 1}-{min(i + batch_size, len(isbns))}")

        # Create tasks for this batch
        batch_tasks = [
            scrape_all_sources_async(meta, title) for title, _, meta in batch
        ]

        try:
            # Run batch concurrently
            batch_results = await asyncio.gather(*batch_tasks)

            # Flatten results (each ISBN returns a list of results from different sources)
            for isbn_results in batch_results:
                all_results.extend(isbn_results)

            # Small delay between batches to be respectful to the sites
            if i + batch_size < len(isbns):
                await asyncio.sleep(2)

        except Exception as e:
            scraper_logger.error(f"Error processing batch {i // batch_size + 1}: {e}")

    end_time = time.time()
    duration = end_time - start_time

    successful_results = len([r for r in all_results if r.get("success", False)])
    log_task_complete(scraper_logger, f"Async bulk scraping for {len(isbns)} ISBNs", duration)
    scraper_logger.info(f"Async bulk scraping completed: {successful_results}/{len(all_results)} successful scrapes")

    return all_results


def save_results_to_csv(results: list[dict]):
    """
    Save scraping results to CSV file, ensuring only one scrape per day is saved.
    If a scrape is manually initiated, it overwrites the past data of the same day.

    Args:
        results: List of scraping result dictionaries
    """
    if not results:
        scraper_logger.warning("No results to save")
        return

    try:
        # Ensure data directory exists
        DATA_DIR.mkdir(exist_ok=True)

        # Add timestamp to results
        timestamp = datetime.now().isoformat()
        today_str = datetime.now().date().isoformat()
        for result in results:
            result["timestamp"] = timestamp

        # Convert to DataFrame
        new_df = pd.DataFrame(results)

        # Remove any existing records for today
        if PRICES_CSV.exists():
            existing_df = pd.read_csv(PRICES_CSV)
            if "timestamp" in existing_df.columns:
                # Keep only records not from today
                existing_df["date"] = pd.to_datetime(existing_df["timestamp"]).dt.date.astype(str)
                filtered_df = existing_df[existing_df["date"] != today_str].drop(columns=["date"])
            else:
                filtered_df = existing_df
            combined_df = pd.concat([filtered_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        # Save to CSV
        combined_df.to_csv(PRICES_CSV, index=False)
        scraper_logger.info(f"Saved {len(results)} new price records to {PRICES_CSV}")

    except Exception as e:
        scraper_logger.error(f"Error saving results to CSV: {e}")


def load_isbns_from_file(filepath: str = None) -> list[tuple[str, str, dict]]:
    """Load book/ISBN combinations from ``books.json``.

    Args:
        filepath: Path to the books file (defaults to ``books.json`` in the
            project root)

    Returns:
        A list of ``(title, isbn, metadata)`` tuples
    """
    if filepath is None:
        filepath = BASE_DIR / "books.json"

    try:
        with open(filepath, "r") as f:
            books = json.load(f)

        results: list[tuple[str, str, dict]] = []
        for title, isbn_list in books.items():
            for item in isbn_list:
                for isbn, meta in item.items():
                    results.append((title, str(isbn), meta))

        scraper_logger.info(f"Loaded {len(results)} ISBNs from {filepath}")
        return results

    except FileNotFoundError:
        scraper_logger.warning(f"Books file not found: {filepath}")
        return []
    except Exception as e:
        scraper_logger.error(f"Error loading ISBNs from file: {e}")
        return []


async def scrape_all_isbns_async(isbn_file: str = None) -> None:
    """
    Async scrape all ISBNs from file across all sources with improved performance

    Args:
        isbn_file: Path to ISBNs file (optional)
    """
    log_task_start(scraper_logger, "Starting async full ISBN scraping job")
    start_time = time.time()
    
    # Initialize ChromeDriver session once at the start
    scraper_logger.info("Initializing ChromeDriver session for bulk scraping...")
    if not initialize_chromedriver_session():
        scraper_logger.error("Failed to initialize ChromeDriver session, aborting scraping")
        return

    # Load ISBNs
    isbns = load_isbns_from_file(isbn_file)

    if not isbns:
        scraper_logger.warning("No ISBNs to scrape")
        return

    # Scrape all ISBNs concurrently with controlled batching
    all_results = await scrape_multiple_isbns(isbns)

    # Save all results at once
    if all_results:
        save_results_to_csv(all_results)

    end_time = time.time()
    duration = end_time - start_time

    successful_results = len([r for r in all_results if r.get("success", False)])
    total_attempts = len(all_results)

    log_task_complete(scraper_logger, "Async full ISBN scraping job", duration)
    scraper_logger.info(f"Async scraping completed: {successful_results}/{total_attempts} successful scrapes")


# Remove the sync wrapper and make scrape_all_isbns async
scrape_all_isbns = scrape_all_isbns_async


# Sync wrapper functions for backward compatibility
def scrape_christianbook_sync(isbn: dict, book_title: str = "") -> dict:
    """Sync wrapper for scrape_christianbook_async"""
    return asyncio.run(scrape_christianbook_async(isbn, book_title))


def scrape_rainbowresource_sync(isbn: dict, book_title: str = "") -> dict:
    """Sync wrapper for scrape_rainbowresource_async"""
    return asyncio.run(scrape_rainbowresource_async(isbn, book_title))


def scrape_abebooks_sync(isbn: dict, book_title: str = "") -> dict:
    """Sync wrapper for scrape_abebooks_async"""
    return asyncio.run(scrape_abebooks_async(isbn, book_title))


def scrape_camelcamelcamel_sync(isbn: dict, book_title: str = "") -> dict:
    """Sync wrapper for scrape_camelcamelcamel_async"""
    return asyncio.run(scrape_camelcamelcamel_async(isbn, book_title))


def scrape_all_sources_sync(isbn: dict, book_title: str = "") -> list[dict]:
    """
    Sync wrapper for scrape_all_sources_async - maintains backward compatibility

    Args:
        isbn: The ISBN to scrape

    Returns:
        List of result dictionaries from all sources
    """
    return asyncio.run(scrape_all_sources_async(isbn, book_title))


# Backward compatibility: Export sync versions under original names
scrape_christianbook = scrape_christianbook_sync
scrape_rainbowresource = scrape_rainbowresource_sync
scrape_abebooks = scrape_abebooks_sync
scrape_camelcamelcamel = scrape_camelcamelcamel_sync
scrape_all_sources = scrape_all_sources_sync


if __name__ == "__main__":
    # Test the async scrapers
    test_isbn = "9780134685991"  # Effective Java

    async def test_async_scrapers():
        print("Testing async scraper functions...")
        
        # Initialize ChromeDriver session once at the start of testing
        print("\n0. Initializing ChromeDriver session...")
        if initialize_chromedriver_session():
            print("   ✅ ChromeDriver session initialized successfully")
        else:
            print("   ❌ Failed to initialize ChromeDriver session")
            return

        # Test individual scrapers
        print("\n1. Testing async Christianbook...")
        result = await scrape_christianbook_async(test_isbn)
        print(f"   Result: {result}")

        print("\n2. Testing async RainbowResource...")
        result = await scrape_rainbowresource_async(test_isbn)
        print(f"   Result: {result}")

        print("\n3. Testing async all sources (concurrent)...")
        all_results = await scrape_all_sources_async(test_isbn)
        save_results_to_csv(all_results)
        print(f"   Saved {len(all_results)} results to CSV")

        print("\n4. Testing multiple ISBNs async...")
        test_isbns = [test_isbn, "9780132350884"]  # Add another test ISBN
        multiple_results = await scrape_multiple_isbns(test_isbns, batch_size=2)
        print(f"   Processed {len(test_isbns)} ISBNs, got {len(multiple_results)} total results")

    # Run the async test
    asyncio.run(test_async_scrapers())
