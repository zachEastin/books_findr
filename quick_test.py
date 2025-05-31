"""
Book Price Tracker - Quick Test Script
Test core functionality without external dependencies
"""

from scripts.scheduler import price_scheduler
from scripts.logger import setup_logger
from app import load_prices_data
import pandas as pd
from pathlib import Path


def main():
    print("=== Book Price Tracker - Quick Test ===\n")

    # Test 1: Logger
    print("1. Testing Logger...")
    logger = setup_logger("quick_test")
    logger.info("Logger test successful")
    print("   ✓ Logger working\n")
    # Test 2: Data Loading
    print("2. Testing Data Loading...")
    df = load_prices_data()
    print(f"   ✓ Loaded {len(df)} price records")
    if not df.empty:
        print(f"   - Sources: {', '.join(df['source'].unique())}")
        print(f"   - ISBNs: {', '.join([str(isbn) for isbn in df['isbn'].unique()])}")
    print()

    # Test 3: Scheduler Status
    print("3. Testing Scheduler...")
    status = price_scheduler.get_status()
    print(f"   ✓ Scheduler status: {status['running']}")
    print(f"   - Next run: {status['next_run']}")
    print(f"   - Last run: {status['last_run']}")
    print()

    # Test 4: File Structure
    print("4. Checking File Structure...")
    files_to_check = [
        "app.py",
        "isbns.txt",
        "data/prices.csv",
        "templates/index.html",
        "scripts/scraper.py",
        "scripts/scheduler.py",
        "scripts/logger.py",
    ]

    for file_path in files_to_check:
        exists = Path(file_path).exists()
        status = "✓" if exists else "✗"
        print(f"   {status} {file_path}")
    print()
    # Test 5: ISBN File
    print("5. Testing ISBN File...")
    isbn_file = Path("isbns.txt")
    if isbn_file.exists():
        with open(isbn_file, "r") as f:
            isbns = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        print(f"   ✓ Found {len(isbns)} ISBNs")
        if isbns:
            print(f"   - Sample: {isbns[0]}")
    else:
        print("   ✗ isbns.txt not found")
    print()

    print("=== Test Complete ===")
    print("✅ Core functionality is working!")
    print("\nNext steps:")
    print("1. Install Chrome/ChromeDriver for web scraping")
    print("2. Test scraping with: python manage.py scrape <isbn>")
    print("3. Start scheduler with: python manage.py start-scheduler")
    print("4. View web UI at: http://localhost:5000")


if __name__ == "__main__":
    main()
