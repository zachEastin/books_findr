"""
Book Price Tracker - Simple HTTP Scraper
Alternative scraper using requests + BeautifulSoup (no Selenium required)
"""

import requests
from bs4 import BeautifulSoup
import time
import re
from typing import Dict, Optional
from pathlib import Path

from scripts.logger import scraper_logger, log_scrape_result


# Headers to mimic a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

TIMEOUT = 10


def clean_price(price_text: str) -> Optional[float]:
    """Extract numeric price from text"""
    if not price_text:
        return None

    # Remove common currency symbols and text
    cleaned = re.sub(r"[^\d.,]", "", price_text.replace(",", ""))

    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def scrape_openlibrary_info(isbn: str) -> Dict:
    """
    Get book information from OpenLibrary (free API)
    This provides title and basic info, not prices
    """
    result = {
        "isbn": isbn,
        "source": "OpenLibrary",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    try:
        # OpenLibrary API
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        result["url"] = url

        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()

        data = response.json()
        book_key = f"ISBN:{isbn}"

        if book_key in data:
            book_info = data[book_key]
            result["title"] = book_info.get("title", "Unknown Title")
            result["success"] = True
            result["notes"] = "Book info retrieved from OpenLibrary"
            result["price"] = 0.0  # OpenLibrary doesn't have prices
        else:
            result["notes"] = "Book not found in OpenLibrary"

    except requests.RequestException as e:
        result["notes"] = f"Request error: {str(e)}"
    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"

    log_scrape_result(scraper_logger, isbn, "OpenLibrary", result["success"], result["price"], result["notes"])
    return result


def scrape_amazon_simple(isbn: str) -> Dict:
    """
    Simple Amazon scraper using search
    Note: This is for testing - Amazon has anti-bot measures
    """
    result = {
        "isbn": isbn,
        "source": "Amazon",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    try:
        # Amazon search URL
        search_url = f"https://www.amazon.com/s?k={isbn}"
        result["url"] = search_url

        session = requests.Session()
        session.headers.update(HEADERS)

        response = session.get(search_url, timeout=TIMEOUT)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Look for search results
        search_results = soup.find_all("div", {"data-component-type": "s-search-result"})

        if search_results:
            first_result = search_results[0]

            # Try to find title
            title_element = first_result.find("h2", class_="a-size-mini")
            if title_element:
                title_link = title_element.find("a")
                if title_link:
                    result["title"] = title_link.get_text(strip=True)

            # Try to find price
            price_elements = first_result.find_all("span", class_="a-price-whole")
            if price_elements:
                price_text = price_elements[0].get_text(strip=True)
                price_value = clean_price(price_text)
                if price_value:
                    result["price"] = price_value
                    result["success"] = True
                    result["notes"] = "Found price in Amazon search results"
                else:
                    result["notes"] = f"Invalid price format: {price_text}"
            else:
                result["notes"] = "No price found in search results"
        else:
            result["notes"] = "No search results found"

    except requests.RequestException as e:
        result["notes"] = f"Request error: {str(e)}"
    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"

    log_scrape_result(scraper_logger, isbn, "Amazon", result["success"], result["price"], result["notes"])
    return result


def test_simple_scrapers(isbn: str = "9780134685991"):
    """Test the simple HTTP-based scrapers"""
    print(f"Testing simple scrapers for ISBN: {isbn}")
    print("=" * 50)

    # Test OpenLibrary
    print("1. Testing OpenLibrary...")
    result1 = scrape_openlibrary_info(isbn)
    print(f"   Success: {result1['success']}")
    print(f"   Title: {result1['title']}")
    print(f"   Notes: {result1['notes']}")
    print()

    # Test Amazon (be careful - may be blocked)
    print("2. Testing Amazon (simple)...")
    result2 = scrape_amazon_simple(isbn)
    print(f"   Success: {result2['success']}")
    print(f"   Title: {result2['title']}")
    print(f"   Price: ${result2['price']}" if result2["price"] else "No price")
    print(f"   Notes: {result2['notes']}")
    print()

    return [result1, result2]


if __name__ == "__main__":
    # Test with a known ISBN
    test_isbn = "9780134685991"  # Effective Java
    results = test_simple_scrapers(test_isbn)

    print("Test completed!")
    successful = len([r for r in results if r["success"]])
    print(f"Results: {successful}/{len(results)} successful")
