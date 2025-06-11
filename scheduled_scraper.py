"""
Standalone scraper for scheduled execution
Run this script via Windows Task Scheduler or cron
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add the project directory to Python path
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

# Setup logging for scheduled runs
LOGS_DIR = PROJECT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "scheduled_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """Main entry point for scheduled scraping"""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Starting scheduled price scraping at {start_time}")
    
    try:
        # Import scraper functions (scrape_all_isbns is now async)
        from scripts.scraper import scrape_all_isbns_async, load_isbns_from_file
        
        # Load ISBNs to scrape
        isbns = load_isbns_from_file()
        if not isbns:
            logger.warning("No ISBNs found to scrape - check isbns.json file")
            return
            
        logger.info(f"Found {len(isbns)} ISBNs to scrape")
        
        # Log ISBN details
        for isbn, metadata in isbns.items():
            title = metadata.get('title', 'Unknown Title')
            logger.info(f"  - {isbn}: {title}")
        
        # Run the bulk scraping (using the async version)
        logger.info("Starting bulk scraping process...")
        await scrape_all_isbns_async()
        
        end_time = datetime.now()
        duration = end_time - start_time
        logger.info(f"Scheduled scraping completed successfully in {duration}")
        logger.info("=" * 60)
        
    except ImportError as e:
        logger.error(f"Failed to import scraper modules: {e}")
        logger.error("Make sure you're running this from the correct directory")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Error during scheduled scraping: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)

def test_imports():
    """Test that all required modules can be imported"""
    try:
        from scripts.scraper import scrape_all_isbns_async, load_isbns_from_file
        # Test that we can call load_isbns_from_file
        isbns = load_isbns_from_file()
        logger.info("SUCCESS: Successfully imported scraper modules")
        logger.info(f"SUCCESS: Found {len(isbns)} ISBNs in isbns.json")
        return True
    except ImportError as e:
        logger.error(f"ERROR: Failed to import scraper modules: {e}")
        return False

if __name__ == "__main__":
    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            logger.info("Testing scheduled scraper setup...")
            if test_imports():
                logger.info("SUCCESS: Scheduled scraper is ready to run")
                sys.exit(0)
            else:
                logger.error("ERROR: Scheduled scraper setup has issues")
                sys.exit(1)
        elif sys.argv[1] == "--help":
            print("Scheduled Book Price Scraper")
            print("Usage:")
            print("  python scheduled_scraper.py        # Run the scraper")
            print("  python scheduled_scraper.py --test # Test the setup")
            print("  python scheduled_scraper.py --help # Show this help")
            sys.exit(0)
    
    # Run the main scraper
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
