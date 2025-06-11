#!/usr/bin/env python3
"""
Book Price Tracker - Complete System Test
Tests all major functionality of the application
"""

import time
import requests
from pathlib import Path
import pandas as pd
import json

# Test configuration
BASE_URL = "http://127.0.0.1:5000"
TEST_ISBN = "1593173350"  # Learning Python by Mark Lutz


def test_basic_api():
    """Test basic API endpoints"""
    print("=== Testing Basic API ===")

    # Test health endpoint
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Health check: {data['status']}")
            print(f"  - Total records: {data['total_records']}")
        else:
            print(f"✗ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Health check error: {e}")


def test_isbn_management():
    """Test ISBN management through API"""
    print("\n=== Testing ISBN Management ===")

    # Get current ISBNs
    try:
        response = requests.get(f"{BASE_URL}/api/isbns")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Current ISBNs: {data['count']} tracked")
            original_count = data["count"]
        else:
            print(f"✗ Failed to get ISBNs: {response.status_code}")
            return
    except Exception as e:
        print(f"✗ ISBN fetch error: {e}")
        return

    # Add test ISBN
    try:
        response = requests.post(f"{BASE_URL}/api/isbns", json={"isbn": TEST_ISBN})
        if response.status_code == 200:
            print(f"✓ Added test ISBN: {TEST_ISBN}")
        else:
            data = response.json()
            print(f"⚠ Add ISBN response: {data.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"✗ Add ISBN error: {e}")

    # Verify addition
    try:
        response = requests.get(f"{BASE_URL}/api/isbns")
        if response.status_code == 200:
            data = response.json()
            new_count = data["count"]
            if TEST_ISBN in data["isbns"]:
                print(f"✓ ISBN verified in list ({new_count} total)")
            else:
                print(f"⚠ ISBN not found in list")
        else:
            print(f"✗ Failed to verify ISBN")
    except Exception as e:
        print(f"✗ ISBN verification error: {e}")


def test_price_data():
    """Test price data endpoints"""
    print("\n=== Testing Price Data ===")

    # Test price data endpoint
    try:
        response = requests.get(f"{BASE_URL}/api/prices")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Price data loaded: {len(data)} records")

            if data:
                # Show sample record
                sample = data[0]
                print(f"  - Sample: {sample.get('isbn')} from {sample.get('source')}")
        else:
            print(f"✗ Failed to get price data: {response.status_code}")
    except Exception as e:
        print(f"✗ Price data error: {e}")

    # Test recent prices
    try:
        response = requests.get(f"{BASE_URL}/api/prices/recent")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Recent prices: {len(data)} records")
        else:
            print(f"✗ Failed to get recent prices: {response.status_code}")
    except Exception as e:
        print(f"✗ Recent prices error: {e}")


def test_web_interface():
    """Test web interface accessibility"""
    print("\n=== Testing Web Interface ===")

    # Test main dashboard
    try:
        response = requests.get(BASE_URL)
        if response.status_code == 200:
            print("✓ Main dashboard accessible")
        else:
            print(f"✗ Dashboard failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Dashboard error: {e}")

    # Test admin panel
    try:
        response = requests.get(f"{BASE_URL}/admin")
        if response.status_code == 200:
            print("✓ Admin panel accessible")
        else:
            print(f"✗ Admin panel failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Admin panel error: {e}")


def test_data_files():
    """Test data file integrity"""
    print("\n=== Testing Data Files ===")

    # Check CSV file
    csv_file = Path("data/prices.csv")
    if csv_file.exists():
        try:
            df = pd.read_csv(csv_file)
            print(f"✓ CSV file readable: {len(df)} records")

            # Check required columns
            required_cols = ["timestamp", "isbn", "source", "price"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if not missing_cols:
                print("✓ All required columns present")
            else:
                print(f"⚠ Missing columns: {missing_cols}")

        except Exception as e:
            print(f"✗ CSV read error: {e}")
    else:
        print("✗ CSV file not found")

    # Check books file
    books_file = Path("books.json")
    if books_file.exists():
        try:
            with open(books_file, "r") as f:
                books = json.load(f)
            print(f"✓ Books file readable: {len(books)} books")
        except Exception as e:
            print(f"✗ Books file error: {e}")
    else:
        print("✗ Books file not found")


def test_manual_scrape():
    """Test manual scraping trigger (optional)"""
    print("\n=== Testing Manual Scrape (Optional) ===")

    # This is optional since it takes time and may fail
    user_input = input("Test manual scraping? This will take 30-60 seconds (y/N): ").lower()

    if user_input == "y":
        try:
            print(f"Triggering scrape for {TEST_ISBN}...")
            response = requests.post(f"{BASE_URL}/api/scrape/{TEST_ISBN}")

            if response.status_code == 200:
                data = response.json()
                print(f"✓ Scrape completed: {data.get('message')}")
                print(f"  - Results: {data.get('results_count', 0)}")
            else:
                data = response.json()
                print(f"⚠ Scrape issues: {data.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"✗ Manual scrape error: {e}")
    else:
        print("⚠ Manual scrape skipped")


def cleanup():
    """Clean up test data"""
    print("\n=== Cleanup ===")

    # Remove test ISBN
    try:
        response = requests.delete(f"{BASE_URL}/api/isbns/{TEST_ISBN}")
        if response.status_code == 200:
            print(f"✓ Removed test ISBN: {TEST_ISBN}")
        else:
            print(f"⚠ Cleanup note: {TEST_ISBN} may not have been removed")
    except Exception as e:
        print(f"⚠ Cleanup error: {e}")


def main():
    """Run complete system test"""
    print("🚀 Book Price Tracker - Complete System Test")
    print("=" * 50)
    print()

    # Check if server is running
    try:
        response = requests.get(BASE_URL, timeout=5)
        print(f"✓ Server is running at {BASE_URL}")
    except requests.exceptions.RequestException:
        print(f"✗ Server not accessible at {BASE_URL}")
        print("Please start the server with: python app.py")
        return

    # Run all tests
    test_basic_api()
    test_isbn_management()
    test_price_data()
    test_web_interface()
    test_data_files()
    test_manual_scrape()
    cleanup()

    print("\n" + "=" * 50)
    print("🎉 Complete System Test Finished!")
    print("\nNext steps:")
    print("1. View dashboard: http://127.0.0.1:5000")
    print("2. Manage ISBNs: http://127.0.0.1:5000/admin")
    print("3. Schedule daily scraping: python manage.py schedule --start 09:00")
    print("4. Monitor logs in the logs/ directory")


if __name__ == "__main__":
    main()
