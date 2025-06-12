# Enhanced Browser Pool for Selenium Scraping

This enhancement provides persistent browser sessions with comprehensive GPU/WebGL disabling for optimal headless Chrome performance.

## Key Features

### 🚀 **Persistent Browser Sessions**
- Reuse browser instances across multiple scrapes
- Eliminate startup overhead (2-5 seconds per browser launch)
- Configurable pool size and session management

### ⚡ **Optimized Chrome Options**
- Comprehensive GPU/WebGL disabling for better performance
- New headless mode (`--headless=new`)
- Memory and performance optimizations
- Anti-detection measures

### 📊 **Pool Management**
- Source-specific browser pools (one per website)
- Batch processing with configurable batch sizes
- Session lifecycle management (age/idle timeouts)
- Real-time pool statistics

## Quick Start

### 1. Enhanced Chrome Options (Drop-in Replacement)

Replace your existing Chrome options with the optimized version:

```python
from simple_enhanced_scraper import get_optimized_chrome_options

# In your existing scraper
chrome_options = get_optimized_chrome_options()
driver = webdriver.Chrome(service=service, options=chrome_options)
```

### 2. Enhanced Batch Scraping

Use the enhanced batch scraper for bulk operations:

```python
from simple_enhanced_scraper import enhanced_scrape_multiple_isbns

# Your ISBN data
isbn_list = [
    {"isbn13": "9780134685991", "title": "Effective Java"},
    {"isbn13": "9780132350884", "title": "Clean Code"},
    # ... more ISBNs
]

# Enhanced batch scraping
results = await enhanced_scrape_multiple_isbns(isbn_list, batch_size=5)
```

### 3. Source-Specific Pools

For advanced usage with source-specific browser pools:

```python
from enhanced_browser_pool import get_enhanced_browser_pool, initialize_source_pools

# Initialize pools for specific sources
sources = ["bookscouter", "christianbook", "rainbowresource"]
initialize_source_pools(sources, pool_size_per_source=2)

# Use source-specific browsers
pool = get_enhanced_browser_pool()
with pool.get_browser(source="bookscouter") as driver:
    # Scrape BookScouter with dedicated browser
    driver.get("https://bookscouter.com/isbn/9780134685991")
    # ... scraping logic
```

## Performance Comparison

### Before (Traditional Approach)
```
📊 10 ISBNs × 4 sources = 40 scrapes
⏱️  Browser startup: ~3 seconds per scrape
🔄 Total overhead: ~120 seconds just for browser startup
```

### After (Enhanced Browser Pool)
```
📊 10 ISBNs × 4 sources = 40 scrapes  
⚡ Browser startup: ~0.1 seconds per scrape (reuse)
🔄 Total overhead: ~4 seconds for browser management
💡 Performance improvement: ~30x faster startup
```

## Comprehensive Chrome Options

The enhanced Chrome options include:

### GPU/WebGL Disabling
```python
--disable-gpu
--disable-gpu-sandbox
--disable-software-rasterizer
--disable-webgl
--disable-webgl2
--disable-3d-apis
--disable-accelerated-2d-canvas
--disable-accelerated-video-decode
--disable-hardware-acceleration
```

### Performance Optimizations
```python
--headless=new                    # New headless mode
--memory-pressure-off             # Reduce memory pressure
--max_old_space_size=4096        # Increase heap size
--disable-background-timer-throttling
--disable-renderer-backgrounding
--disable-features=VizDisplayCompositor
```

### Anti-Detection
```python
--disable-blink-features=AutomationControlled
--user-agent=Mozilla/5.0...       # Realistic user agent
navigator.webdriver = undefined   # Hide automation
```

## Example Usage

### Basic Enhanced Scraping
```python
import asyncio
from simple_enhanced_scraper import enhanced_scrape_multiple_isbns

async def main():
    isbn_list = [
        {"isbn13": "9780134685991", "title": "Effective Java"},
        {"isbn13": "9780132350884", "title": "Clean Code"},
    ]
    
    # Enhanced scraping with persistent browsers
    results = await enhanced_scrape_multiple_isbns(isbn_list, batch_size=2)
    
    print(f"Scraped {len(results)} results")
    for result in results:
        if result.get('success'):
            print(f"✅ {result['source']}: ${result.get('price', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Performance Demo
Run the performance comparison:

```bash
python simple_enhanced_scraper.py
```

This will demonstrate:
- Browser pool initialization
- Batch processing with persistent sessions
- Performance metrics and statistics
- Success rates by source

## Integration with Existing Code

### Option 1: Minimal Changes
Just replace your Chrome options:

```python
# OLD
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")

# NEW
from simple_enhanced_scraper import get_optimized_chrome_options
chrome_options = get_optimized_chrome_options()
```

### Option 2: Enhanced Batch Processing
Replace bulk scraping functions:

```python
# OLD
results = []
for isbn in isbn_list:
    result = scrape_isbn(isbn)  # Creates new browser each time
    results.extend(result)

# NEW
results = await enhanced_scrape_multiple_isbns(isbn_list, batch_size=5)
```

### Option 3: Full Source-Specific Pools
Use the complete enhanced browser pool system:

```python
from enhanced_browser_pool import EnhancedScrapingManager

manager = EnhancedScrapingManager(pool_size=4, sources_pool_size=2)
manager.initialize()

# Scrape with persistent, source-specific browsers
results = await manager.scrape_batch(isbn_list, batch_size=5)
manager.shutdown()
```

## Configuration Options

### Browser Pool Settings
```python
# Pool sizes
GENERAL_POOL_SIZE = 4           # General purpose browsers
SOURCE_POOL_SIZE = 2            # Browsers per source
BATCH_SIZE = 5                  # ISBNs per batch

# Session timeouts
SESSION_MAX_AGE = 300           # 5 minutes
SESSION_IDLE_TIMEOUT = 60       # 1 minute
```

### Chrome Options Customization
```python
# Disable images for faster loading (optional)
chrome_options.add_argument("--disable-images")

# Enable JavaScript debugging (optional)
chrome_options.add_argument("--enable-logging")
chrome_options.add_argument("--log-level=0")
```

## Monitoring and Statistics

Get real-time pool statistics:

```python
from enhanced_browser_pool import get_enhanced_browser_pool

pool = get_enhanced_browser_pool()
stats = pool.get_pool_stats()

print(f"Total sessions: {stats['total_sessions']}")
print(f"Available sessions: {stats['general_available']}")

for session_id, details in stats['sessions_detail'].items():
    print(f"{session_id}: {details['use_count']} uses, age {details['age']:.1f}s")
```

## Benefits Summary

1. **Performance**: 20-30x faster startup times
2. **Resource Efficiency**: Reuse browser instances
3. **Stability**: Session health monitoring and auto-restart
4. **Scalability**: Source-specific pools for concurrent scraping
5. **Monitoring**: Real-time statistics and pool health
6. **Compatibility**: Drop-in replacement for existing code

## Files Created

- `enhanced_browser_pool.py` - Complete enhanced browser pool system
- `simple_enhanced_scraper.py` - Simple integration with existing code
- `example_enhanced_scraping.py` - Full example with source-specific pools
- `README_ENHANCED_BROWSER_POOL.md` - This documentation

Start with `simple_enhanced_scraper.py` for the easiest integration, then move to the full enhanced browser pool system for maximum performance.
