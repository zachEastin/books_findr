#!/usr/bin/env python3
"""
Example: Using Enhanced Browser Pool for Efficient Scraping
This demonstrates how to integrate the enhanced browser pool with your existing scraper
"""

import asyncio
import time
from typing import List, Dict
from enhanced_browser_pool import (
    get_enhanced_browser_pool, 
    initialize_source_pools,
    scrape_multiple_isbns_enhanced
)

# Import your existing scraper functions
try:
    from scripts.scraper import (
        initialize_browser_pool,
        get_browser_pool_stats,
        shutdown_browser_pool,
        scrape_all_sources_async
    )
    from scripts.logger import scraper_logger
except ImportError:
    print("Could not import existing scraper - using standalone mode")
    scraper_logger = None


class EnhancedScrapingManager:
    """Manages enhanced scraping operations with persistent browser pools"""
    
    def __init__(self, pool_size: int = 4, sources_pool_size: int = 2):
        self.pool_size = pool_size
        self.sources_pool_size = sources_pool_size
        self.pool = None
        self.sources = ["bookscouter", "christianbook", "rainbowresource", "abebooks"]
        self.initialized = False
    
    def initialize(self) -> bool:
        """Initialize the enhanced browser pool system"""
        try:
            print(f"🚀 Initializing enhanced browser pool (size: {self.pool_size})...")
            
            # Get the global pool
            self.pool = get_enhanced_browser_pool()
            
            # Initialize source-specific pools
            print(f"📚 Setting up source-specific pools ({self.sources_pool_size} browsers per source)...")
            if not initialize_source_pools(self.sources, self.sources_pool_size):
                print("❌ Failed to initialize source pools")
                return False
            
            self.initialized = True
            print("✅ Enhanced browser pool system initialized successfully!")
            
            # Print initial stats
            self.print_pool_stats()
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize enhanced browser pool: {e}")
            return False
    
    def print_pool_stats(self):
        """Print current pool statistics"""
        if not self.pool:
            return
        
        stats = self.pool.get_pool_stats()
        print("\n📊 Current Pool Statistics:")
        print(f"   Total browser sessions: {stats['total_sessions']}")
        print(f"   General pool available: {stats['general_available']}")
        
        if stats['source_pools']:
            print("   Source-specific pools:")
            for source, available in stats['source_pools'].items():
                print(f"     {source}: {available} available")
        
        print("   Session details:")
        for session_id, details in stats['sessions_detail'].items():
            age = details['age']
            idle = details['idle_time']
            print(f"     {session_id}: {details['use_count']} uses, "
                  f"age {age:.1f}s, idle {idle:.1f}s, healthy: {details['is_healthy']}")
    
    async def scrape_single_isbn(self, isbn_data: Dict) -> List[Dict]:
        """Scrape a single ISBN across all sources using pool"""
        if not self.initialized:
            raise Exception("Pool not initialized. Call initialize() first.")
        
        isbn = isbn_data.get('isbn13', isbn_data.get('isbn', 'unknown'))
        print(f"\n🔍 Scraping ISBN: {isbn}")
        
        results = []
        start_time = time.time()
        
        # Scrape each source concurrently using the pool
        tasks = []
        for source in self.sources:
            task = self._scrape_source_async(isbn_data, source)
            tasks.append(task)
        
        # Wait for all scraping tasks to complete
        source_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(source_results):
            if isinstance(result, Exception):
                print(f"   ❌ {self.sources[i]}: {result}")
                results.append({
                    'isbn': isbn,
                    'source': self.sources[i],
                    'error': str(result),
                    'success': False
                })
            else:
                success_icon = "✅" if result.get('success') else "❌"
                price = result.get('price', 'N/A')
                print(f"   {success_icon} {result['source']}: ${price}")
                results.append(result)
        
        elapsed = time.time() - start_time
        print(f"   ⏱️  Completed in {elapsed:.2f} seconds")
        
        return results
    
    async def _scrape_source_async(self, isbn_data: Dict, source: str) -> Dict:
        """Scrape a specific source using browser pool"""
        isbn = isbn_data.get('isbn13', isbn_data.get('isbn', ''))
        
        try:
            # Get browser from source-specific pool
            with self.pool.get_browser(source=source, timeout=10.0) as driver:
                return await self._perform_scraping(driver, isbn_data, source)
                
        except Exception as e:
            return {
                'isbn': isbn,
                'source': source,
                'error': str(e),
                'success': False,
                'timestamp': time.time()
            }
    
    async def _perform_scraping(self, driver, isbn_data: Dict, source: str) -> Dict:
        """Perform actual scraping for a source (placeholder implementation)"""
        isbn = isbn_data.get('isbn13', isbn_data.get('isbn', ''))
        
        # This would integrate with your existing scraping logic
        # For now, we'll simulate the scraping process
        
        try:
            if source == "bookscouter":
                url = f"https://bookscouter.com/isbn/{isbn}"
                driver.get(url)
                # Add your BookScouter scraping logic here
                # result = scrape_bookscouter_logic(driver, isbn_data)
                
            elif source == "christianbook":
                url = f"https://www.christianbook.com/apps/search?Ntt={isbn}"
                driver.get(url)
                # Add your Christianbook scraping logic here
                # result = scrape_christianbook_logic(driver, isbn_data)
                
            elif source == "rainbowresource":
                url = f"https://www.rainbowresource.com/search?query={isbn}"
                driver.get(url)
                # Add your RainbowResource scraping logic here
                # result = scrape_rainbowresource_logic(driver, isbn_data)
                
            elif source == "abebooks":
                url = f"https://www.abebooks.com/servlet/SearchResults?isbn={isbn}"
                driver.get(url)
                # Add your AbeBooks scraping logic here
                # result = scrape_abebooks_logic(driver, isbn_data)
            
            # Simulate processing time
            await asyncio.sleep(0.5)
            
            # Return simulated result (replace with actual scraping)
            return {
                'isbn': isbn,
                'source': source,
                'title': driver.title,
                'url': driver.current_url,
                'price': 19.99,  # Simulated price
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
    
    async def scrape_batch(self, isbn_list: List[Dict], batch_size: int = 5) -> List[Dict]:
        """Scrape multiple ISBNs in batches"""
        if not self.initialized:
            raise Exception("Pool not initialized. Call initialize() first.")
        
        print(f"\n📦 Starting batch scraping: {len(isbn_list)} ISBNs, batch size: {batch_size}")
        
        all_results = []
        total_batches = (len(isbn_list) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(isbn_list))
            batch = isbn_list[start_idx:end_idx]
            
            print(f"\n🔄 Processing batch {batch_num + 1}/{total_batches} ({len(batch)} ISBNs)")
            batch_start = time.time()
            
            # Process batch concurrently
            batch_tasks = []
            for isbn_data in batch:
                task = self.scrape_single_isbn(isbn_data)
                batch_tasks.append(task)
            
            batch_results = await asyncio.gather(*batch_tasks)
            
            # Flatten results
            for isbn_results in batch_results:
                all_results.extend(isbn_results)
            
            batch_elapsed = time.time() - batch_start
            print(f"   ✅ Batch {batch_num + 1} completed in {batch_elapsed:.2f} seconds")
            
            # Print pool stats after each batch
            if batch_num % 2 == 0:  # Every 2 batches
                self.print_pool_stats()
            
            # Brief pause between batches to be respectful
            if batch_num < total_batches - 1:
                await asyncio.sleep(1.0)
        
        print(f"\n🎉 Batch scraping complete! Processed {len(all_results)} total results")
        return all_results
    
    def shutdown(self):
        """Shutdown the browser pool"""
        if self.pool:
            print("\n🔄 Shutting down browser pool...")
            self.pool.shutdown()
            print("✅ Browser pool shutdown complete")


async def demo_enhanced_scraping():
    """Demonstrate enhanced scraping with persistent browser pools"""
    print("=== Enhanced Browser Pool Scraping Demo ===")
    
    # Initialize the scraping manager
    manager = EnhancedScrapingManager(pool_size=4, sources_pool_size=2)
    
    if not manager.initialize():
        print("Failed to initialize scraping manager")
        return
    
    # Test data - replace with your actual ISBN data
    test_isbns = [
        {"isbn13": "9780134685991", "title": "Effective Java"},
        {"isbn13": "9780132350884", "title": "Clean Code"}, 
        {"isbn13": "9781593279509", "title": "Eloquent JavaScript"},
        {"isbn13": "9780596517748", "title": "JavaScript: The Good Parts"},
        {"isbn13": "9781449331818", "title": "Learning JavaScript Design Patterns"}
    ]
    
    try:
        # Test 1: Single ISBN scraping
        print("\n" + "="*50)
        print("TEST 1: Single ISBN Scraping")
        print("="*50)
        
        single_results = await manager.scrape_single_isbn(test_isbns[0])
        print(f"Single ISBN results: {len(single_results)} sources scraped")
        
        # Test 2: Batch scraping
        print("\n" + "="*50)
        print("TEST 2: Batch Scraping")
        print("="*50)
        
        batch_results = await manager.scrape_batch(test_isbns, batch_size=2)
        print(f"Batch results: {len(batch_results)} total results")
        
        # Test 3: Performance comparison
        print("\n" + "="*50)
        print("TEST 3: Performance Analysis")
        print("="*50)
        
        manager.print_pool_stats()
        
        # Calculate some basic metrics
        successful_results = [r for r in batch_results if r.get('success')]
        success_rate = len(successful_results) / len(batch_results) * 100
        print(f"\n📈 Success rate: {success_rate:.1f}%")
        print(f"📊 Total successful scrapes: {len(successful_results)}")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Always shutdown the pool
        manager.shutdown()
    
    print("\n✅ Enhanced scraping demo complete!")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(demo_enhanced_scraping())
