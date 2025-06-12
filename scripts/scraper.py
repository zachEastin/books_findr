"""
Book Price Tracker - Async Web Scraping Module
Handles scraping from BookScouter, Christianbook, RainbowResource, and CamelCamelCamel
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
from typing import Optional, Dict
import os
import stat
import subprocess
import threading
import queue
import atexit
from contextlib import contextmanager

from .logger import scraper_logger, log_scrape_result, log_task_start, log_task_complete
import json


# Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PRICES_CSV = DATA_DIR / "prices.csv"
TIMEOUT = 15  # seconds
MAX_CONCURRENT_SCRAPERS = 3  # Limit concurrent scrapers to be respectful

# Browser Pool Configuration
BROWSER_POOL_SIZE = 4  # Number of persistent browser sessions
BROWSER_SESSION_TIMEOUT = 300  # 5 minutes - restart browsers after this time
BROWSER_IDLE_TIMEOUT = 60  # 1 minute - return browser to pool after idle time

# Shared thread pool for running blocking Selenium calls
executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SCRAPERS)

# Global ChromeDriver management - initialize once and reuse throughout session
_chromedriver_path = None
_chromedriver_lock = threading.Lock()
_chromedriver_initialized = False

# Global Browser Pool Management
_browser_pool = None
_browser_pool_lock = threading.Lock()


class BrowserSession:
    """Represents a single browser session with lifecycle management"""
    def __init__(self, browser_id: str):
        self.browser_id = browser_id
        self.driver = None
        self.created_at = time.time()
        self.last_used = time.time()
        self.use_count = 0
        self.is_healthy = True
        self._lock = threading.Lock()
    
    def create_driver(self) -> bool:
        """Create a new Chrome driver instance with optimized settings"""
        try:
            driver_path = _initialize_chromedriver_once()
            if not driver_path:
                raise Exception("ChromeDriver initialization failed")
            
            # Configure Chrome options for optimal headless performance
            chrome_options = Options()
            
            # Headless mode - run in background
            chrome_options.add_argument("--headless=new")  # Use new headless mode
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            # GPU and WebGL optimizations for better performance
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-gpu-sandbox")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-webgl")
            chrome_options.add_argument("--disable-webgl2")
            chrome_options.add_argument("--disable-3d-apis")
            chrome_options.add_argument("--disable-accelerated-2d-canvas")
            chrome_options.add_argument("--disable-accelerated-video-decode")
            chrome_options.add_argument("--disable-accelerated-video-encode")
            chrome_options.add_argument("--disable-accelerated-mjpeg-decode")
            chrome_options.add_argument("--disable-hardware-acceleration")
            
            # Memory and performance optimizations
            chrome_options.add_argument("--memory-pressure-off")
            chrome_options.add_argument("--max_old_space_size=4096")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-features=TranslateUI")
            chrome_options.add_argument("--disable-ipc-flooding-protection")
            
            # Resource optimizations (but keep JS enabled for modern sites)
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-default-apps")
            chrome_options.add_argument("--disable-sync")
            
            # User agent for better compatibility
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Anti-detection measures
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Create service using the pre-initialized ChromeDriver path
            service = Service(executable_path=driver_path)
            
            # Create the WebDriver instance
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(TIMEOUT)
            
            # Hide automation indicators
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.created_at = time.time()
            self.last_used = time.time()
            self.is_healthy = True
            
            scraper_logger.info(f"Created browser session {self.browser_id}")
            return True
            
        except Exception as e:
            scraper_logger.error(f"Failed to create browser session {self.browser_id}: {e}")
            self.is_healthy = False
            return False
    
    def is_expired(self) -> bool:
        """Check if browser session has expired and needs restart"""
        age = time.time() - self.created_at
        idle_time = time.time() - self.last_used
        return (age > BROWSER_SESSION_TIMEOUT or 
                idle_time > BROWSER_IDLE_TIMEOUT or 
                not self.is_healthy or 
                self.driver is None)
    
    def restart(self) -> bool:
        """Restart the browser session"""
        with self._lock:
            self.cleanup()
            return self.create_driver()
    
    def cleanup(self):
        """Clean up browser resources"""
        if self.driver:
            try:
                self.driver.quit()
                scraper_logger.debug(f"Cleaned up browser session {self.browser_id}")
            except Exception as e:
                scraper_logger.warning(f"Error cleaning up browser session {self.browser_id}: {e}")
            finally:
                self.driver = None
                self.is_healthy = False
    
    def mark_used(self):
        """Mark the session as recently used"""
        self.last_used = time.time()
        self.use_count += 1
    
    def get_driver(self) -> Optional[webdriver.Chrome]:
        """Get the driver instance if healthy"""
        with self._lock:
            if self.is_expired():
                if not self.restart():
                    return None
            self.mark_used()
            return self.driver


class BrowserPool:
    """Manages a pool of persistent browser sessions"""
    
    def __init__(self, pool_size: int = BROWSER_POOL_SIZE):
        self.pool_size = pool_size
        self.sessions: Dict[str, BrowserSession] = {}
        self.available_sessions: queue.Queue = queue.Queue()
        self.all_sessions_created = False
        self._lock = threading.Lock()
        self._shutdown = False
        
        # Register cleanup function
        atexit.register(self.shutdown)
    
    def _create_session(self, session_id: str) -> BrowserSession:
        """Create a new browser session"""
        session = BrowserSession(session_id)
        if session.create_driver():
            return session
        else:
            session.cleanup()
            raise Exception(f"Failed to create browser session {session_id}")
    
    def _ensure_pool_initialized(self):
        """Ensure the browser pool is fully initialized"""
        if self.all_sessions_created or self._shutdown:
            return
            
        with self._lock:
            if self.all_sessions_created or self._shutdown:
                return
                
            scraper_logger.info(f"Initializing browser pool with {self.pool_size} sessions...")
            
            # Create all browser sessions
            created_sessions = []
            for i in range(self.pool_size):
                session_id = f"browser_session_{i+1}"
                try:
                    session = self._create_session(session_id)
                    self.sessions[session_id] = session
                    self.available_sessions.put(session_id)
                    created_sessions.append(session_id)
                    scraper_logger.debug(f"Created browser session {session_id}")
                except Exception as e:
                    scraper_logger.error(f"Failed to create browser session {session_id}: {e}")
            
            self.all_sessions_created = True
            scraper_logger.info(f"Browser pool initialized with {len(created_sessions)} sessions")
    
    @contextmanager
    def get_browser(self, timeout: float = 30.0):
        """Get a browser from the pool (context manager)"""
        if self._shutdown:
            raise Exception("Browser pool is shutdown")
            
        self._ensure_pool_initialized()
        
        session_id = None
        session = None
        
        try:
            # Get an available session
            session_id = self.available_sessions.get(timeout=timeout)
            session = self.sessions.get(session_id)
            
            if not session:
                raise Exception(f"Session {session_id} not found in pool")
            
            # Get the driver (this will restart if expired)
            driver = session.get_driver()
            if not driver:
                raise Exception(f"Failed to get healthy driver from session {session_id}")
            
            scraper_logger.debug(f"Acquired browser session {session_id} (used {session.use_count} times)")
            yield driver
            
        except queue.Empty:
            raise Exception(f"No browser available within {timeout} seconds - pool may be exhausted")
        except Exception as e:
            scraper_logger.error(f"Error getting browser from pool: {e}")
            raise
        finally:
            # Return session to pool
            if session_id and not self._shutdown:
                try:
                    # Check if session is still healthy before returning to pool
                    if session and session.is_healthy and not session.is_expired():
                        self.available_sessions.put(session_id)
                        scraper_logger.debug(f"Returned browser session {session_id} to pool")
                    else:
                        # Session is unhealthy, try to restart it
                        if session:
                            scraper_logger.warning(f"Browser session {session_id} is unhealthy, attempting restart...")
                            if session.restart():
                                self.available_sessions.put(session_id)
                                scraper_logger.info(f"Restarted and returned browser session {session_id} to pool")
                            else:
                                scraper_logger.error(f"Failed to restart browser session {session_id}, removing from pool")
                                # Don't put it back in the queue
                except Exception as e:
                    scraper_logger.error(f"Error returning browser session {session_id} to pool: {e}")
    
    def get_pool_stats(self) -> Dict:
        """Get statistics about the browser pool"""
        stats = {
            'pool_size': self.pool_size,
            'total_sessions': len(self.sessions),
            'available_sessions': self.available_sessions.qsize(),
            'sessions_detail': {}
        }
        
        for session_id, session in self.sessions.items():
            stats['sessions_detail'][session_id] = {
                'use_count': session.use_count,
                'age': time.time() - session.created_at,
                'idle_time': time.time() - session.last_used,
                'is_healthy': session.is_healthy,
                'is_expired': session.is_expired()
            }
        
        return stats
    
    def restart_all_sessions(self):
        """Restart all browser sessions in the pool"""
        scraper_logger.info("Restarting all browser sessions...")
        
        with self._lock:
            # Clear the available queue
            while not self.available_sessions.empty():
                try:
                    self.available_sessions.get_nowait()
                except queue.Empty:
                    break
            
            # Restart all sessions
            restarted = 0
            for session_id, session in self.sessions.items():
                if session.restart():
                    self.available_sessions.put(session_id)
                    restarted += 1
                else:
                    scraper_logger.error(f"Failed to restart session {session_id}")
            
            scraper_logger.info(f"Restarted {restarted}/{len(self.sessions)} browser sessions")
    
    def shutdown(self):
        """Shutdown the browser pool and clean up all sessions"""
        if self._shutdown:
            return
            
        scraper_logger.info("Shutting down browser pool...")
        self._shutdown = True
        
        with self._lock:
            for session_id, session in self.sessions.items():
                session.cleanup()
            
            self.sessions.clear()
            
            # Clear the queue
            while not self.available_sessions.empty():
                try:
                    self.available_sessions.get_nowait()
                except queue.Empty:
                    break
        
        scraper_logger.info("Browser pool shutdown complete")


def get_browser_pool() -> BrowserPool:
    """Get the global browser pool instance (singleton)"""
    global _browser_pool
    
    if _browser_pool is None:
        with _browser_pool_lock:
            if _browser_pool is None:
                _browser_pool = BrowserPool(BROWSER_POOL_SIZE)
    
    return _browser_pool


def initialize_browser_pool(pool_size: int = BROWSER_POOL_SIZE) -> bool:
    """
    Initialize the browser pool with the specified size.
    Call this once at the start of your scraping session for optimal performance.
    
    Args:
        pool_size: Number of browser sessions to create in the pool
        
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    global _browser_pool
    
    try:
        # First ensure ChromeDriver is initialized
        if not initialize_chromedriver_session():
            scraper_logger.error("Failed to initialize ChromeDriver session")
            return False
        
        # Create the browser pool
        with _browser_pool_lock:
            if _browser_pool is not None:
                scraper_logger.info("Browser pool already initialized, shutting down existing pool...")
                _browser_pool.shutdown()
            
            _browser_pool = BrowserPool(pool_size)
            _browser_pool._ensure_pool_initialized()
        
        scraper_logger.info(f"Browser pool initialized successfully with {pool_size} sessions")
        return True
        
    except Exception as e:
        scraper_logger.error(f"Failed to initialize browser pool: {e}")
        return False


def get_browser_pool_stats() -> Dict:
    """Get statistics about the current browser pool"""
    pool = get_browser_pool()
    return pool.get_pool_stats()


def restart_browser_pool():
    """Restart all browser sessions in the pool"""
    pool = get_browser_pool()
    pool.restart_all_sessions()


def shutdown_browser_pool():
    """Shutdown the browser pool"""
    global _browser_pool
    if _browser_pool:
        _browser_pool.shutdown()
        _browser_pool = None


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


def _scrape_bookscouter_sync(search_term: str, url: str) -> dict:
    """Synchronous helper function for BookScouter scraping using browser pool"""
    result_update = {
        "price": None,
        "title": None,
        "notes": "",
        "success": False,
    }

    try:
        pool = get_browser_pool()
        with pool.get_browser() as driver:
            scraper_logger.info(f"Scraping BookScouter for term: {search_term}")

            driver.get(url)

            # Wait for page to load
            WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # Wait 5 seconds for dynamic content to load
            time.sleep(5)

            # Try to find book title
            try:
                title_element = driver.find_element(By.CSS_SELECTOR, "h1, .BookDetailsTitle_bdlrv61")
                result_update["title"] = title_element.text.strip()
            except NoSuchElementException:
                scraper_logger.warning(f"Could not find title for term `{search_term}` on BookScouter")

            # Try to find the lowest price
            try:
                # Look for price elements (BookScouter typically shows prices in a table)
                price_elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    "[class^='BestVendorPrice'], [class*='BestVendorPrice']",
                )

                prices = []
                for element in price_elements:
                    price_text = element.text.strip()
                    price_value = clean_price(price_text)
                    if price_value and price_value > 0:
                        prices.append(price_value)

                if prices:
                    result_update["price"] = min(prices)  # Get lowest selling price
                    result_update["success"] = True
                    result_update["notes"] = f"Found {len(prices)} prices, showing lowest: ${result_update['price']:.2f}"
                else:
                    result_update["notes"] = "No valid prices found"

            except NoSuchElementException:
                result_update["notes"] = "Price elements not found"

    except TimeoutException:
        result_update["notes"] = "Page load timeout"
        scraper_logger.error(f"Timeout scraping BookScouter for term {search_term}")
    except WebDriverException as e:
        result_update["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping BookScouter for term {search_term}: {e}")
    except Exception as e:
        result_update["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping BookScouter for term {search_term}: {e}")

    return result_update


def _scrape_christianbook_sync(search_term: str, search_url: str) -> dict:
    """Synchronous helper function for Christianbook scraping using browser pool"""
    result_update = {
        "price": None,
        "title": None,
        "url": search_url,
        "notes": "",
        "success": False,
    }

    try:
        pool = get_browser_pool()
        with pool.get_browser() as driver:
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

    return result_update


def _scrape_rainbowresource_sync(search_term: str, search_url: str) -> dict:
    """Synchronous helper function for RainbowResource scraping using browser pool"""
    result_update = {
        "price": None,
        "title": None,
        "url": search_url,
        "notes": "",
        "success": False,
    }

    try:
        pool = get_browser_pool()
        with pool.get_browser() as driver:
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

    return result_update


def _scrape_abebooks_sync(search_term: str, search_url: str) -> dict:
    """Synchronous helper function for AbeBooks scraping using browser pool"""
    result_update = {
        "price": None,
        "title": None,
        "url": search_url,
        "notes": "",
        "success": False,
    }

    try:
        pool = get_browser_pool()
        with pool.get_browser() as driver:
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

    return result_update


def _scrape_camelcamelcamel_sync(isbn: str, search_url: str) -> dict:
    """Synchronous helper function for CamelCamelCamel scraping using browser pool"""
    result_update = {
        "price": None,
        "title": None,
        "url": search_url,
        "notes": "",
        "success": False,
    }

    try:
        pool = get_browser_pool()
        with pool.get_browser() as driver:
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

    return result_update


# Async scraper functions
async def scrape_bookscouter_async(isbn_data: dict, book_title: str = "") -> dict:
    """
    Async scrape book price from BookScouter with enhanced search strategies

    Args:
        isbn: The ISBN to search for

    Returns:
        dictionary with scraping results
    """
    result = {
        "isbn": isbn_data.get("isbn13"),
        "book_title": book_title,
        "source": "BookScouter",
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
            f"BookScouter: Trying {len(search_strategies)} search strategies for {isbn_data.get('title', isbn_data.get('isbn13', 'unknown'))}"
        )

        # Try each search strategy until we find results
        for search_term, strategy_name in search_strategies:
            try:
                # BookScouter uses direct ISBN lookup in URL
                url = f"https://bookscouter.com/book/{search_term}?type=buy"
                result["url"] = url

                scraper_logger.info(f"BookScouter: Trying {strategy_name} with term '{search_term}'")

                loop = asyncio.get_running_loop()
                scraping_result = await loop.run_in_executor(
                    executor, _scrape_bookscouter_sync, search_term, url
                )

                if scraping_result.get("success"):
                    result.update(scraping_result)
                    result["notes"] = f"Found using {strategy_name}: {result['notes']}"
                    scraper_logger.info(f"BookScouter: Success with {strategy_name}")
                    break
                else:
                    scraper_logger.info(
                        f"BookScouter: No results with {strategy_name} for term {search_term} and url {url}"
                    )

            except Exception as e:
                scraper_logger.warning(f"BookScouter: Error with {strategy_name}: {e}")
                continue

        if not result["success"]:
            result["notes"] = f"No results found with any search strategy (tried {len(search_strategies)} methods)"

    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(
            f"Unexpected error scraping BookScouter for ISBN {isbn_data.get('isbn13', 'unknown')}: {e}"
        )

    log_scrape_result(
        scraper_logger,
        isbn_data.get("isbn13", "unknown"),
        "BookScouter",
        result["success"],
        result["price"],
        result["notes"],
    )
    return result


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
        scrape_bookscouter_async(isbn, book_title),
        scrape_christianbook_async(isbn, book_title),
        scrape_rainbowresource_async(isbn, book_title),
        scrape_abebooks_async(isbn, book_title),
        # scrape_camelcamelcamel_async(isbn),  # Uncomment to include CamelCamelCamel
    ]

    try:
        # Run all scrapers concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle any exceptions
        processed_results = []
        source_names = ["BookScouter", "Christianbook", "RainbowResource", "AbeBooks"]  # , "CamelCamelCamel"]

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
    Async scrape multiple ISBNs with controlled concurrency using browser pool

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
    
    # Initialize browser pool for batch processing
    if not initialize_browser_pool(BROWSER_POOL_SIZE):
        scraper_logger.error("Failed to initialize browser pool for batch processing")
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

    # Log browser pool statistics
    pool_stats = get_browser_pool_stats()
    scraper_logger.info(f"Browser pool statistics: {pool_stats['available_sessions']}/{pool_stats['total_sessions']} sessions available")

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
    Async scrape all ISBNs from file across all sources with browser pool for improved performance

    Args:
        isbn_file: Path to ISBNs file (optional)
    """
    log_task_start(scraper_logger, "Starting async full ISBN scraping job")
    start_time = time.time()
    
    # Initialize browser pool once at the start
    scraper_logger.info("Initializing browser pool for bulk scraping...")
    if not initialize_browser_pool(BROWSER_POOL_SIZE):
        scraper_logger.error("Failed to initialize browser pool, aborting scraping")
        return

    # Load ISBNs
    isbns = load_isbns_from_file(isbn_file)

    if not isbns:
        scraper_logger.warning("No ISBNs to scrape")
        return

    # Scrape all ISBNs concurrently with controlled batching using browser pool
    all_results = await scrape_multiple_isbns(isbns)

    # Save all results at once
    if all_results:
        save_results_to_csv(all_results)

    end_time = time.time()
    duration = end_time - start_time

    successful_results = len([r for r in all_results if r.get("success", False)])
    total_attempts = len(all_results)

    # Log final browser pool statistics
    pool_stats = get_browser_pool_stats()
    scraper_logger.info(f"Final browser pool statistics: {pool_stats}")

    log_task_complete(scraper_logger, "Async full ISBN scraping job", duration)
    scraper_logger.info(f"Async scraping completed: {successful_results}/{total_attempts} successful scrapes")
    
    # Optional: Shutdown browser pool after bulk operation
    # Uncomment the next line if you want to clean up the pool immediately after bulk scraping
    # shutdown_browser_pool()


# Remove the sync wrapper and make scrape_all_isbns async
scrape_all_isbns = scrape_all_isbns_async


# Sync wrapper functions for backward compatibility
def scrape_bookscouter_sync(isbn: dict, book_title: str = "") -> dict:
    """Sync wrapper for scrape_bookscouter_async"""
    return asyncio.run(scrape_bookscouter_async(isbn, book_title))


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
scrape_bookscouter = scrape_bookscouter_sync
scrape_christianbook = scrape_christianbook_sync
scrape_rainbowresource = scrape_rainbowresource_sync
scrape_abebooks = scrape_abebooks_sync
scrape_camelcamelcamel = scrape_camelcamelcamel_sync
scrape_all_sources = scrape_all_sources_sync


if __name__ == "__main__":
    # Test the async scrapers with browser pool
    test_isbn = {"isbn13": "9780134685991", "title": "Effective Java"}  # Test with proper metadata structure

    async def test_async_scrapers():
        print("Testing async scraper functions with browser pool...")
        
        # Test 1: Initialize browser pool
        print("\n1. Initializing browser pool...")
        if initialize_browser_pool(BROWSER_POOL_SIZE):
            print(f"   ✅ Browser pool initialized successfully with {BROWSER_POOL_SIZE} sessions")
        else:
            print("   ❌ Failed to initialize browser pool")
            return

        # Test 2: Test individual scrapers        
        print("\n2. Testing async BookScouter...")
        result = await scrape_bookscouter_async(test_isbn)
        print(f"   Result: {result}")

        print("\n3. Testing async Christianbook...")
        result = await scrape_christianbook_async(test_isbn)
        print(f"   Result: {result}")

        print("\n4. Testing async RainbowResource...")
        result = await scrape_rainbowresource_async(test_isbn)
        print(f"   Result: {result}")

        print("\n5. Testing async all sources (concurrent)...")
        all_results = await scrape_all_sources_async(test_isbn)
        save_results_to_csv(all_results)
        print(f"   Saved {len(all_results)} results to CSV")

        # Test 3: Check browser pool stats
        print("\n6. Browser pool statistics:")
        stats = get_browser_pool_stats()
        print(f"   Pool size: {stats['pool_size']}")
        print(f"   Available sessions: {stats['available_sessions']}")
        print(f"   Total sessions: {stats['total_sessions']}")
        
        # Test 4: Multiple ISBNs
        print("\n7. Testing multiple ISBNs async...")
        test_isbns = [
            ("Effective Java", "9780134685991", test_isbn),
            ("Clean Code", "9780132350884", {"isbn13": "9780132350884", "title": "Clean Code"})
        ]
        multiple_results = await scrape_multiple_isbns(test_isbns, batch_size=2)
        print(f"   Processed {len(test_isbns)} ISBNs, got {len(multiple_results)} total results")

        # Test 5: Final browser pool stats
        print("\n8. Final browser pool statistics:")
        final_stats = get_browser_pool_stats()
        for session_id, details in final_stats['sessions_detail'].items():
            print(f"   {session_id}: used {details['use_count']} times, age {details['age']:.1f}s, idle {details['idle_time']:.1f}s")

        print("\n9. Shutting down browser pool...")
        shutdown_browser_pool()
        print("   ✅ Browser pool shutdown complete")

        print("\n✅ All tests completed successfully!")

    # Run the async test
    asyncio.run(test_async_scrapers())
