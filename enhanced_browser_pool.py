#!/usr/bin/env python3
"""
Enhanced Browser Pool Management for Web Scraping
Provides source-specific and batch-based persistent browser sessions
"""

import time
import threading
import queue
import atexit
from contextlib import contextmanager
from typing import Dict, Optional, List, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
import stat
import subprocess

# Import your existing logger
try:
    from scripts.logger import scraper_logger
except ImportError:
    import logging
    scraper_logger = logging.getLogger(__name__)


class EnhancedBrowserSession:
    """Enhanced browser session with source-specific optimizations"""
    
    def __init__(self, session_id: str, source: str = "general"):
        self.session_id = session_id
        self.source = source
        self.driver = None
        self.created_at = time.time()
        self.last_used = time.time()
        self.use_count = 0
        self.is_healthy = True
        self.lock = threading.Lock()
        
    def create_driver(self) -> bool:
        """Create Chrome driver with enhanced options"""
        try:
            driver_path = self._get_chromedriver_path()
            if not driver_path:
                raise Exception("ChromeDriver not available")
            
            chrome_options = self._get_chrome_options()
            service = Service(executable_path=driver_path)
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(15)
            
            # Anti-automation detection
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.created_at = time.time()
            self.last_used = time.time()
            self.is_healthy = True
            
            scraper_logger.info(f"Created enhanced browser session {self.session_id} for {self.source}")
            return True
            
        except Exception as e:
            scraper_logger.error(f"Failed to create browser session {self.session_id}: {e}")
            self.is_healthy = False
            return False
    
    def _get_chrome_options(self) -> Options:
        """Get optimized Chrome options for headless scraping"""
        chrome_options = Options()
        
        # Headless mode with new implementation
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # GPU and WebGL optimizations - comprehensive disabling
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-gpu-sandbox")
        chrome_options.add_argument("--disable-software-rasterizer")  
        chrome_options.add_argument("--disable-webgl")
        chrome_options.add_argument("--disable-webgl2")
        chrome_options.add_argument("--disable-3d-apis")
        chrome_options.add_argument("--disable-accelerated-2d-canvas")
        chrome_options.add_argument("--disable-accelerated-video-decode")
        chrome_options.add_argument("--disable-accelerated-video-encode")
        chrome_options.add_argument("--disable-hardware-acceleration")
        
        # Memory and performance optimizations
        chrome_options.add_argument("--memory-pressure-off")
        chrome_options.add_argument("--max_old_space_size=4096")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI,VizDisplayCompositor")
        
        # Resource optimizations
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        
        # Source-specific optimizations
        if self.source in ["bookscouter", "christianbook"]:
            # These sites might need images
            pass  # Keep images enabled
        else:
            # Disable images for faster loading on other sites
            chrome_options.add_argument("--disable-images")
        
        # User agent
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Anti-detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Additional privacy and performance options
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-client-side-phishing-detection")
        chrome_options.add_argument("--disable-component-update")
        chrome_options.add_argument("--disable-domain-reliability")
        
        return chrome_options
    
    def _get_chromedriver_path(self) -> Optional[str]:
        """Get ChromeDriver path (simplified for example)"""
        try:
            return ChromeDriverManager().install()
        except Exception as e:
            scraper_logger.error(f"ChromeDriver initialization failed: {e}")
            return None
    
    def get_driver(self) -> Optional[webdriver.Chrome]:
        """Get healthy driver instance"""
        with self.lock:
            if self.is_expired() or not self.driver:
                if not self.restart():
                    return None
            self.mark_used()
            return self.driver
    
    def mark_used(self):
        """Mark session as recently used"""
        self.last_used = time.time()
        self.use_count += 1
    
    def is_expired(self) -> bool:
        """Check if session needs restart"""
        age = time.time() - self.created_at
        idle_time = time.time() - self.last_used
        return (age > 300 or  # 5 minutes max age
                idle_time > 60 or  # 1 minute max idle
                not self.is_healthy)
    
    def restart(self) -> bool:
        """Restart the browser session"""
        self.cleanup()
        return self.create_driver()
    
    def cleanup(self):
        """Clean up browser resources"""
        if self.driver:
            try:
                self.driver.quit()
                scraper_logger.debug(f"Cleaned up session {self.session_id}")
            except Exception as e:
                scraper_logger.warning(f"Error cleaning up session {self.session_id}: {e}")
            finally:
                self.driver = None
                self.is_healthy = False


class EnhancedBrowserPool:
    """Enhanced browser pool with source-specific and batch management"""
    
    def __init__(self, pool_size: int = 4):
        self.pool_size = pool_size
        self.sessions: Dict[str, EnhancedBrowserSession] = {}
        self.available_sessions: Dict[str, queue.Queue] = {}  # source -> queue
        self.general_sessions: queue.Queue = queue.Queue()
        self.lock = threading.Lock()
        self.shutdown_flag = False
        
        # Register cleanup
        atexit.register(self.shutdown)
        
        # Initialize general pool
        self._initialize_general_pool()
    
    def _initialize_general_pool(self):
        """Initialize general purpose browser sessions"""
        scraper_logger.info(f"Initializing general browser pool with {self.pool_size} sessions...")
        
        for i in range(self.pool_size):
            session_id = f"general_session_{i+1}"
            session = EnhancedBrowserSession(session_id, "general")
            
            if session.create_driver():
                self.sessions[session_id] = session
                self.general_sessions.put(session_id)
                scraper_logger.debug(f"Created general session {session_id}")
            else:
                scraper_logger.error(f"Failed to create general session {session_id}")
    
    def get_source_pool(self, source: str, pool_size: int = 2) -> bool:
        """Initialize source-specific browser pool"""
        if source in self.available_sessions:
            return True  # Already initialized
        
        scraper_logger.info(f"Initializing {source} browser pool with {pool_size} sessions...")
        
        with self.lock:
            if source in self.available_sessions:
                return True
            
            self.available_sessions[source] = queue.Queue()
            
            for i in range(pool_size):
                session_id = f"{source}_session_{i+1}"
                session = EnhancedBrowserSession(session_id, source)
                
                if session.create_driver():
                    self.sessions[session_id] = session
                    self.available_sessions[source].put(session_id)
                    scraper_logger.debug(f"Created {source} session {session_id}")
                else:
                    scraper_logger.error(f"Failed to create {source} session {session_id}")
        
        return True
    
    @contextmanager
    def get_browser(self, source: str = "general", timeout: float = 30.0):
        """Get browser from pool with source preference"""
        session_id = None
        session = None
        
        try:
            # Try source-specific pool first
            if source != "general" and source in self.available_sessions:
                try:
                    session_id = self.available_sessions[source].get(timeout=5.0)
                    session = self.sessions.get(session_id)
                except queue.Empty:
                    pass  # Fall back to general pool
            
            # Fall back to general pool
            if not session_id:
                session_id = self.general_sessions.get(timeout=timeout)
                session = self.sessions.get(session_id)
            
            if not session:
                raise Exception(f"Session {session_id} not found")
            
            driver = session.get_driver()
            if not driver:
                raise Exception(f"Failed to get driver from session {session_id}")
            
            scraper_logger.debug(f"Acquired {source} browser session {session_id}")
            yield driver
            
        except queue.Empty:
            raise Exception(f"No browser available for {source} within {timeout} seconds")
        except Exception as e:
            scraper_logger.error(f"Error getting browser for {source}: {e}")
            raise
        finally:
            # Return session to appropriate pool
            if session_id and session and not self.shutdown_flag:
                try:
                    if session.source != "general" and session.source in self.available_sessions:
                        self.available_sessions[session.source].put(session_id)
                    else:
                        self.general_sessions.put(session_id)
                    scraper_logger.debug(f"Returned session {session_id} to pool")
                except Exception as e:
                    scraper_logger.error(f"Error returning session to pool: {e}")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get comprehensive pool statistics"""
        stats = {
            'total_sessions': len(self.sessions),
            'general_available': self.general_sessions.qsize(),
            'source_pools': {},
            'sessions_detail': {}
        }
        
        # Source-specific stats
        for source, queue_obj in self.available_sessions.items():
            stats['source_pools'][source] = queue_obj.qsize()
        
        # Individual session stats
        for session_id, session in self.sessions.items():
            stats['sessions_detail'][session_id] = {
                'source': session.source,
                'use_count': session.use_count,
                'age': time.time() - session.created_at,
                'idle_time': time.time() - session.last_used,
                'is_healthy': session.is_healthy
            }
        
        return stats
    
    def shutdown(self):
        """Shutdown all browser sessions"""
        if self.shutdown_flag:
            return
        
        scraper_logger.info("Shutting down enhanced browser pool...")
        self.shutdown_flag = True
        
        with self.lock:
            for session in self.sessions.values():
                session.cleanup()
            self.sessions.clear()
            self.available_sessions.clear()
        
        scraper_logger.info("Enhanced browser pool shutdown complete")


# Global pool instance
_enhanced_pool = None
_pool_lock = threading.Lock()


def get_enhanced_browser_pool() -> EnhancedBrowserPool:
    """Get or create global enhanced browser pool"""
    global _enhanced_pool
    
    with _pool_lock:
        if _enhanced_pool is None:
            _enhanced_pool = EnhancedBrowserPool()
    
    return _enhanced_pool


def initialize_source_pools(sources: List[str], pool_size_per_source: int = 2) -> bool:
    """Initialize browser pools for specific sources"""
    pool = get_enhanced_browser_pool()
    
    for source in sources:
        if not pool.get_source_pool(source, pool_size_per_source):
            scraper_logger.error(f"Failed to initialize pool for {source}")
            return False
    
    return True


# Example usage functions
async def scrape_multiple_isbns_enhanced(isbn_list: List[Dict], batch_size: int = 5) -> List[Dict]:
    """Enhanced batch scraping with persistent browser pools"""
    results = []
    
    # Initialize source-specific pools
    sources = ["bookscouter", "christianbook", "rainbowresource", "abebooks"]
    initialize_source_pools(sources, pool_size_per_source=2)
    
    pool = get_enhanced_browser_pool()
    
    # Process ISBNs in batches
    for i in range(0, len(isbn_list), batch_size):
        batch = isbn_list[i:i + batch_size]
        batch_results = []
        
        scraper_logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} ISBNs")
        
        # Process each ISBN in the batch
        for isbn_data in batch:
            isbn = isbn_data.get('isbn13', isbn_data.get('isbn', ''))
            
            # Scrape each source using source-specific pools
            for source in sources:
                try:
                    with pool.get_browser(source=source) as driver:
                        result = await scrape_source_with_session(driver, isbn_data, source)
                        batch_results.append(result)
                        
                except Exception as e:
                    scraper_logger.error(f"Error scraping {source} for ISBN {isbn}: {e}")
                    batch_results.append({
                        'isbn': isbn,
                        'source': source,
                        'error': str(e),
                        'success': False
                    })
        
        results.extend(batch_results)
        
        # Brief pause between batches
        if i + batch_size < len(isbn_list):
            time.sleep(1.0)
    
    # Print final statistics
    stats = pool.get_pool_stats()
    scraper_logger.info(f"Batch scraping complete. Pool stats: {stats}")
    
    return results


async def scrape_source_with_session(driver: webdriver.Chrome, isbn_data: Dict, source: str) -> Dict:
    """Scrape a specific source using provided browser session"""
    # This would contain your actual scraping logic for each source
    # For example purposes, here's a simplified version
    
    isbn = isbn_data.get('isbn13', isbn_data.get('isbn', ''))
    
    try:
        if source == "bookscouter":
            url = f"https://bookscouter.com/isbn/{isbn}"
        elif source == "christianbook":
            url = f"https://www.christianbook.com/apps/search?Ntt={isbn}"
        # Add other sources...
        else:
            url = f"https://example.com/search?isbn={isbn}"
        
        driver.get(url)
        time.sleep(2)  # Wait for page load
        
        # Your scraping logic here...
        # This is just a placeholder
        title = driver.title
        
        return {
            'isbn': isbn,
            'source': source,
            'title': title,
            'url': url,
            'success': True,
            'timestamp': time.time()
        }
        
    except Exception as e:
        return {
            'isbn': isbn,
            'source': source,
            'error': str(e),
            'success': False,
            'timestamp': time.time()
        }


if __name__ == "__main__":
    # Example usage
    print("=== Enhanced Browser Pool Demo ===")
    
    # Test basic pool functionality
    pool = get_enhanced_browser_pool()
    
    # Test general pool
    print("\n1. Testing general browser pool...")
    with pool.get_browser() as driver:
        driver.get("https://www.google.com")
        print(f"   Page title: {driver.title}")
    
    # Test source-specific pools  
    print("\n2. Testing source-specific pools...")
    sources = ["bookscouter", "christianbook"]
    initialize_source_pools(sources, 1)
    
    for source in sources:
        print(f"   Testing {source} pool...")
        with pool.get_browser(source=source) as driver:
            driver.get("https://www.google.com")
            print(f"   {source} browser title: {driver.title}")
    
    # Print statistics
    print("\n3. Pool statistics:")
    stats = pool.get_pool_stats()
    print(f"   Total sessions: {stats['total_sessions']}")
    print(f"   General available: {stats['general_available']}")
    for source, available in stats['source_pools'].items():
        print(f"   {source} available: {available}")
    
    print("\n✅ Enhanced browser pool demo complete!")
