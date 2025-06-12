#!/usr/bin/env python3
"""
Enhanced Browser Pool - Standalone Demo
This demonstrates persistent browser sessions with optimized Chrome options
"""

import time
import threading
import queue
from contextlib import contextmanager
from typing import Dict, Optional, List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class OptimizedBrowserSession:
    """A single browser session with enhanced Chrome options"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.driver = None
        self.created_at = time.time()
        self.last_used = time.time()
        self.use_count = 0
        self.is_healthy = True
        self.lock = threading.Lock()
    
    def create_driver(self) -> bool:
        """Create Chrome driver with comprehensive optimizations"""
        try:
            # Get ChromeDriver path
            driver_path = ChromeDriverManager().install()
            
            # Enhanced Chrome options
            chrome_options = self._get_optimized_chrome_options()
            service = Service(executable_path=driver_path)
            
            # Create driver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(15)
            
            # Anti-automation detection
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.created_at = time.time()
            self.last_used = time.time()
            self.is_healthy = True
            
            print(f"✅ Created optimized browser session: {self.session_id}")
            return True
        
        except Exception as e:
            print(f"❌ Failed to create session {self.session_id}: {e}")
            self.is_healthy = False
            return False
    
    def _get_optimized_chrome_options(self) -> Options:
        """Get comprehensive Chrome options for optimal headless performance"""
        chrome_options = Options()
        
        # === HEADLESS MODE ===
        chrome_options.add_argument("--headless=new")  # New headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # === COMPREHENSIVE GPU/WEBGL DISABLING ===
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
        
        # === MEMORY & PERFORMANCE OPTIMIZATIONS ===
        chrome_options.add_argument("--memory-pressure-off")
        chrome_options.add_argument("--max_old_space_size=4096")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI,VizDisplayCompositor")
        
        # === RESOURCE OPTIMIZATIONS ===
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-sync")
        
        # === USER AGENT ===
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # === ANTI-DETECTION ===
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        return chrome_options
    
    def get_driver(self) -> Optional[webdriver.Chrome]:
        """Get healthy driver instance"""
        with self.lock:
            if self._is_expired() or not self.driver:
                if not self.restart():
                    return None
            self._mark_used()
            return self.driver
    
    def _mark_used(self):
        """Mark session as recently used"""
        self.last_used = time.time()
        self.use_count += 1
    
    def _is_expired(self) -> bool:
        """Check if session needs restart"""
        age = time.time() - self.created_at
        idle_time = time.time() - self.last_used
        return (age > 300 or idle_time > 60 or not self.is_healthy)
    
    def restart(self) -> bool:
        """Restart the browser session"""
        self.cleanup()
        return self.create_driver()
    
    def cleanup(self):
        """Clean up browser resources"""
        if self.driver:
            try:
                self.driver.quit()
                print(f"🧹 Cleaned up session: {self.session_id}")
            except Exception as e:
                print(f"⚠️ Cleanup warning for {self.session_id}: {e}")
            finally:
                self.driver = None
                self.is_healthy = False


class OptimizedBrowserPool:
    """Pool of persistent browser sessions with optimized Chrome options"""
    
    def __init__(self, pool_size: int = 4):
        self.pool_size = pool_size
        self.sessions: Dict[str, OptimizedBrowserSession] = {}
        self.available_sessions: queue.Queue = queue.Queue()
        self.lock = threading.Lock()
        self.shutdown_flag = False
        
        # Initialize sessions
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize browser pool"""
        print(f"🚀 Initializing optimized browser pool with {self.pool_size} sessions...")
        
        for i in range(self.pool_size):
            session_id = f"optimized_session_{i+1}"
            session = OptimizedBrowserSession(session_id)
            
            if session.create_driver():
                self.sessions[session_id] = session
                self.available_sessions.put(session_id)
            else:
                print(f"❌ Failed to create session {session_id}")
        
        print(f"✅ Pool initialized with {len(self.sessions)} sessions")
    
    @contextmanager
    def get_browser(self, timeout: float = 30.0):
        """Get browser from pool"""
        session_id = None
        session = None
        
        try:
            # Get available session
            session_id = self.available_sessions.get(timeout=timeout)
            session = self.sessions.get(session_id)
            
            if not session:
                raise Exception(f"Session {session_id} not found")
            
            driver = session.get_driver()
            if not driver:
                raise Exception(f"Failed to get driver from {session_id}")
            
            print(f"📱 Using session {session_id} (used {session.use_count} times)")
            yield driver
            
        except queue.Empty:
            raise Exception(f"No browser available within {timeout} seconds")
        except Exception as e:
            print(f"❌ Browser pool error: {e}")
            raise
        finally:
            # Return session to pool
            if session_id and session and not self.shutdown_flag:
                try:
                    if session.is_healthy:
                        self.available_sessions.put(session_id)
                        print(f"♻️ Returned session {session_id} to pool")
                    else:
                        print(f"🔄 Session {session_id} unhealthy, attempting restart...")
                        if session.restart():
                            self.available_sessions.put(session_id)
                            print(f"✅ Restarted and returned session {session_id}")
                except Exception as e:
                    print(f"⚠️ Error returning session to pool: {e}")
    
    def get_stats(self) -> Dict:
        """Get pool statistics"""
        stats = {
            'total_sessions': len(self.sessions),
            'available_sessions': self.available_sessions.qsize(),
            'session_details': {}
        }
        
        for session_id, session in self.sessions.items():
            stats['session_details'][session_id] = {
                'use_count': session.use_count,
                'age': time.time() - session.created_at,
                'idle_time': time.time() - session.last_used,
                'is_healthy': session.is_healthy
            }
        
        return stats
    
    def shutdown(self):
        """Shutdown all sessions"""
        if self.shutdown_flag:
            return
        
        print("🔄 Shutting down browser pool...")
        self.shutdown_flag = True
        
        with self.lock:
            for session in self.sessions.values():
                session.cleanup()
            self.sessions.clear()
        
        print("✅ Browser pool shutdown complete")


def demo_optimized_scraping():
    """Demonstrate optimized browser pool performance"""
    print("=" * 60)
    print("🚀 OPTIMIZED BROWSER POOL DEMONSTRATION")
    print("=" * 60)
    
    # Create optimized browser pool
    pool = OptimizedBrowserPool(pool_size=3)
    
    try:
        # Test URLs to scrape
        test_urls = [
            "https://httpbin.org/user-agent",
            "https://httpbin.org/headers", 
            "https://www.google.com",
            "https://example.com",
            "https://httpbin.org/delay/1"
        ]
        
        print(f"\n📊 Testing with {len(test_urls)} URLs")
        print("⏱️ Measuring performance with persistent browser sessions...")
        
        start_time = time.time()
        
        # Scrape URLs using persistent browser pool
        for i, url in enumerate(test_urls, 1):
            print(f"\n🔍 Test {i}/{len(test_urls)}: {url}")
            
            with pool.get_browser(timeout=10.0) as driver:
                try:
                    driver.get(url)
                    time.sleep(0.5)  # Brief pause
                    
                    title = driver.title or "No title"
                    print(f"   ✅ Success: {title[:50]}...")
                    
                except Exception as e:
                    print(f"   ❌ Error: {e}")
        
        total_time = time.time() - start_time
        
        # Performance analysis
        print(f"\n📈 PERFORMANCE RESULTS:")
        print(f"   ⏱️ Total time: {total_time:.2f} seconds")
        print(f"   📊 Average per URL: {total_time/len(test_urls):.2f} seconds")
        print(f"   🚀 URLs per second: {len(test_urls)/total_time:.2f}")
        
        # Pool statistics
        print(f"\n📊 POOL STATISTICS:")
        stats = pool.get_stats()
        print(f"   🎯 Total sessions: {stats['total_sessions']}")
        print(f"   ♻️ Available sessions: {stats['available_sessions']}")
        
        print(f"\n🔍 SESSION DETAILS:")
        for session_id, details in stats['session_details'].items():
            age = details['age']
            idle = details['idle_time']
            uses = details['use_count']
            health = "✅" if details['is_healthy'] else "❌"
            print(f"   {session_id}: {uses} uses, age {age:.1f}s, idle {idle:.1f}s {health}")
        
        print(f"\n🎉 OPTIMIZATION BENEFITS DEMONSTRATED:")
        print(f"   • Persistent browser sessions (no startup overhead)")
        print(f"   • Comprehensive GPU/WebGL disabling")
        print(f"   • Memory and performance optimizations")
        print(f"   • Anti-detection measures")
        print(f"   • Session lifecycle management")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Always cleanup
        pool.shutdown()
    
    print(f"\n✅ Optimized browser pool demo complete!")


if __name__ == "__main__":
    demo_optimized_scraping()
