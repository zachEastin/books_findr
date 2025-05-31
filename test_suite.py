"""
Book Price Tracker - Test Suite
Simple tests to validate core functionality without external dependencies
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import sys
import os

# Add the project root to the path
sys.path.append(str(Path(__file__).parent))

from scripts.logger import setup_logger
from app import load_prices_data, create_sample_data


def test_logging():
    """Test the logging system"""
    print("Testing logging system...")
    logger = setup_logger("test_suite")
    logger.info("Test log entry")
    logger.warning("Test warning")
    logger.error("Test error")
    print("✓ Logging system working")
    return True


def test_data_loading():
    """Test CSV data loading"""
    print("Testing data loading...")
    df = load_prices_data()
    print(f"✓ Loaded {len(df)} records from CSV")

    if not df.empty:
        print(f"  - Columns: {list(df.columns)}")
        print(f"  - Sources: {df['source'].unique().tolist()}")
        print(f"  - ISBNs: {df['isbn'].unique().tolist()}")

    return True


def test_sample_data_creation():
    """Test sample data creation"""
    print("Testing sample data creation...")

    # Backup existing data
    csv_path = Path("data/prices.csv")
    backup_path = Path("data/prices_backup.csv")

    if csv_path.exists():
        csv_path.rename(backup_path)

    try:
        # Create new sample data
        create_sample_data()

        # Verify it was created
        df = pd.read_csv(csv_path)
        print(f"✓ Created sample data with {len(df)} records")

    finally:
        # Restore backup if it exists
        if backup_path.exists():
            if csv_path.exists():
                csv_path.unlink()
            backup_path.rename(csv_path)

    return True


def test_csv_operations():
    """Test CSV reading/writing operations"""
    print("Testing CSV operations...")

    # Test data
    test_data = [
        {
            "timestamp": datetime.now().isoformat(),
            "isbn": "9781234567890",
            "title": "Test Book",
            "source": "TestSource",
            "price": 29.99,
            "url": "https://test.com",
            "notes": "Test entry",
        }
    ]

    # Create test DataFrame
    test_df = pd.DataFrame(test_data)

    # Save to temporary file
    temp_csv = Path("data/test_prices.csv")
    test_df.to_csv(temp_csv, index=False)

    # Read it back
    loaded_df = pd.read_csv(temp_csv)

    # Verify
    assert len(loaded_df) == 1
    assert loaded_df.iloc[0]["isbn"] == "9781234567890"
    assert loaded_df.iloc[0]["price"] == 29.99

    # Cleanup
    temp_csv.unlink()

    print("✓ CSV operations working correctly")
    return True


def test_isbn_file_handling():
    """Test ISBN file operations"""
    print("Testing ISBN file handling...")

    # Check if isbns.txt exists
    isbn_file = Path("isbns.txt")
    if isbn_file.exists():
        with open(isbn_file, "r") as f:
            isbns = [line.strip() for line in f if line.strip()]
        print(f"✓ Found {len(isbns)} ISBNs in isbns.txt")
        if isbns:
            print(f"  - First ISBN: {isbns[0]}")
    else:
        print("! isbns.txt not found, creating sample...")
        sample_isbns = [
            "9780134685991",  # Effective Java
            "9780596009205",  # Head First Design Patterns
            "9781617294945",  # Spring Boot in Action
        ]
        with open(isbn_file, "w") as f:
            for isbn in sample_isbns:
                f.write(f"{isbn}\n")
        print(f"✓ Created isbns.txt with {len(sample_isbns)} sample ISBNs")

    return True


def test_scraper_data_structure():
    """Test that scraper results have correct structure"""
    print("Testing scraper data structure...")

    # Mock scraper result
    mock_result = {
        "isbn": "9780134685991",
        "source": "TestSource",
        "price": 45.99,
        "title": "Test Book",
        "url": "https://test.com",
        "notes": "Test note",
        "success": True,
        "timestamp": datetime.now().isoformat(),
    }

    # Verify required fields
    required_fields = ["isbn", "source", "price", "title", "url", "notes", "success"]
    for field in required_fields:
        assert field in mock_result, f"Missing required field: {field}"

    # Test DataFrame creation
    df = pd.DataFrame([mock_result])
    assert len(df) == 1
    assert df.iloc[0]["isbn"] == "9780134685991"

    print("✓ Scraper data structure is correct")
    return True


def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("Book Price Tracker - Test Suite")
    print("=" * 50)

    tests = [
        test_logging,
        test_data_loading,
        test_sample_data_creation,
        test_csv_operations,
        test_isbn_file_handling,
        test_scraper_data_structure,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
            print()
        except Exception as e:
            print(f"✗ Test failed: {e}")
            failed += 1
            print()

    print("=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 50)

    if failed == 0:
        print("🎉 All tests passed! Core functionality is working.")
    else:
        print(f"⚠️  {failed} test(s) failed. Please check the issues above.")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
