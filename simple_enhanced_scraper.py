#!/usr/bin/env python3
"""
Simple integration example: Enhance your existing scraper with better Chrome options
This modifies your existing scraper functions to use optimized browser settings
"""

import time
import asyncio
from typing import Dict, List
from selenium.webdriver.chrome.options import Options

# Your existing imports
try:
    from scripts.scraper import (
        initialize_browser_pool,
        get_browser_pool,
        shutdown_browser_pool,
        get_browser_pool_stats,
        scrape_all_sources_async
    )
    from scripts.logger import scraper_logger
except ImportError:
    print("Warning: Could not import existing scraper modules")


def get_optimized_chrome_options() -> Options:
    """
    Enhanced Chrome options for better headless scraping performance
    Comprehensive GPU/WebGL disabling and performance optimizations
    """
    chrome_options = Options()
    
    # === HEADLESS MODE ===
    chrome_options.add_argument("--headless=new")  # Use new headless mode (Chrome 109+)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # === GPU/WEBGL COMPREHENSIVE DISABLING ===
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
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    
    # === MEMORY AND PERFORMANCE OPTIMIZATIONS ===
    chrome_options.add_argument("--memory-pressure-off")
    chrome_options.add_argument("--max_old_space_size=4096")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-features=TranslateUI")
    chrome_options.add_argument("--disable-ipc-flooding-protection")
    
    # === RESOURCE OPTIMIZATIONS ===
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-component-update")
    chrome_options.add_argument("--disable-domain-reliability")
    
    # === OPTIONAL: Disable images for faster loading ===
    # Uncomment if your scraping doesn't need images
    # chrome_options.add_argument("--disable-images")
    
    # === USER AGENT ===
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # === ANTI-DETECTION ===
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # === ADDITIONAL PERFORMANCE OPTIONS ===
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-client-side-phishing-detection")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-prompt-on-repost")
    
    return chrome_options


async def enhanced_scrape_multiple_isbns(isbn_list: List[Dict], batch_size: int = 5) -> List[Dict]:
    """
    Enhanced version of your bulk scraping with optimized browser pool usage
    Processes ISBNs in batches with persistent browser sessions
    """
    print(f"🚀 Enhanced bulk scraping: {len(isbn_list)} ISBNs in batches of {batch_size}")
    
    # Initialize browser pool
    if not initialize_browser_pool():
        raise Exception("Failed to initialize browser pool")
    
    print("✅ Browser pool initialized successfully")
    
    all_results = []
    total_batches = (len(isbn_list) + batch_size - 1) // batch_size
    
    try:
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(isbn_list))
            batch = isbn_list[start_idx:end_idx]
            
            print(f"\n📦 Processing batch {batch_num + 1}/{total_batches}: {len(batch)} ISBNs")
            batch_start_time = time.time()
            
            # Process batch items concurrently
            batch_tasks = []
            for isbn_data in batch:
                # Use your existing async scraping function 
                task = scrape_all_sources_async(isbn_data)
                batch_tasks.append(task)
            
            # Wait for all tasks in batch to complete
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process results and handle exceptions
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    isbn = batch[i].get('isbn13', batch[i].get('isbn', 'unknown'))
                    error_result = {
                        'isbn': isbn,
                        'error': str(result),
                        'success': False,
                        'timestamp': time.time()
                    }
                    all_results.append(error_result)
                    print(f"   ❌ Error processing ISBN {isbn}: {result}")
                else:
                    all_results.extend(result if isinstance(result, list) else [result])
                    isbn = batch[i].get('isbn13', batch[i].get('isbn', 'unknown'))
                    success_count = len([r for r in (result if isinstance(result, list) else [result]) if r.get('success')])
                    print(f"   ✅ ISBN {isbn}: {success_count} successful scrapes")
            
            batch_elapsed = time.time() - batch_start_time
            print(f"   ⏱️  Batch completed in {batch_elapsed:.2f} seconds")
            
            # Print pool statistics every few batches
            if batch_num % 3 == 0:
                stats = get_browser_pool_stats()
                print(f"   📊 Pool stats: {stats['available_sessions']}/{stats['total_sessions']} available")
            
            # Brief pause between batches to be respectful to target sites
            if batch_num < total_batches - 1:
                await asyncio.sleep(1.0)
    
    finally:
        # Always clean up
        print("\n🔄 Shutting down browser pool...")
        shutdown_browser_pool()
        print("✅ Browser pool shutdown complete")
    
    successful_results = [r for r in all_results if r.get('success')]
    success_rate = len(successful_results) / len(all_results) * 100 if all_results else 0
    
    print(f"\n🎉 Enhanced bulk scraping complete!")
    print(f"   📊 Total results: {len(all_results)}")
    print(f"   ✅ Successful: {len(successful_results)} ({success_rate:.1f}%)")
    
    return all_results


async def performance_comparison_demo():
    """
    Demonstrate the performance benefits of the enhanced browser pool
    """
    print("=== Enhanced Browser Pool Performance Demo ===")
    
    # Test data
    test_isbns = [
        {"isbn13": "9780134685991", "title": "Effective Java"},
        {"isbn13": "9780132350884", "title": "Clean Code"},
        {"isbn13": "9781593279509", "title": "Eloquent JavaScript"},
        {"isbn13": "9780596517748", "title": "JavaScript: The Good Parts"},
    ]
    
    print(f"\n📚 Testing with {len(test_isbns)} ISBNs")
    
    # Test 1: Enhanced batch processing
    print("\n" + "="*50)
    print("TEST: Enhanced Batch Processing with Persistent Sessions")
    print("="*50)
    
    start_time = time.time()
    
    try:
        results = await enhanced_scrape_multiple_isbns(test_isbns, batch_size=2)
        
        elapsed_time = time.time() - start_time
        
        print(f"\n📈 Performance Results:")
        print(f"   ⏱️  Total time: {elapsed_time:.2f} seconds")
        print(f"   📊 Results per second: {len(results)/elapsed_time:.2f}")
        print(f"   🔄 Average time per ISBN: {elapsed_time/len(test_isbns):.2f} seconds")
        
        # Analyze results by source
        sources = {}
        for result in results:
            source = result.get('source', 'unknown')
            if source not in sources:
                sources[source] = {'total': 0, 'successful': 0}
            sources[source]['total'] += 1
            if result.get('success'):
                sources[source]['successful'] += 1
        
        print(f"\n📊 Results by Source:")
        for source, stats in sources.items():
            success_rate = stats['successful'] / stats['total'] * 100 if stats['total'] > 0 else 0
            print(f"   {source}: {stats['successful']}/{stats['total']} ({success_rate:.1f}%)")
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Performance demo complete!")


def print_optimization_benefits():
    """Print information about the browser pool optimizations"""
    print("=== Browser Pool Optimization Benefits ===")
    print()
    print("🚀 PERFORMANCE IMPROVEMENTS:")
    print("   • Persistent browser sessions - no startup overhead per scrape")
    print("   • Headless Chrome with new --headless=new flag")
    print("   • Comprehensive GPU/WebGL disabling for better performance")
    print("   • Memory optimizations and background throttling disabled")
    print("   • Browser session reuse across multiple ISBNs")
    print()
    print("⚡ CHROME OPTIONS OPTIMIZATIONS:")
    print("   • --disable-gpu --disable-gpu-sandbox")
    print("   • --disable-webgl --disable-webgl2 --disable-3d-apis")
    print("   • --disable-hardware-acceleration") 
    print("   • --memory-pressure-off --max_old_space_size=4096")
    print("   • --disable-background-timer-throttling")
    print("   • --disable-features=VizDisplayCompositor")
    print()
    print("🔒 ANTI-DETECTION MEASURES:")
    print("   • --disable-blink-features=AutomationControlled")
    print("   • Custom user agent string")
    print("   • Navigator.webdriver property hiding")
    print()
    print("📊 RESOURCE MANAGEMENT:")
    print("   • Browser pool with configurable size")
    print("   • Session lifecycle management (age + idle timeouts)")
    print("   • Automatic session restart for failed browsers")
    print("   • Pool statistics and monitoring")
    print()


if __name__ == "__main__":
    print_optimization_benefits()
    print()
    
    # Run the performance demo
    asyncio.run(performance_comparison_demo())
