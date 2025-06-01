"""
Book Price Tracker - Web Scraping Module
Handles scraping from BookScouter, Christianbook, RainbowResource, and CamelCamelCamel
Now with async/await support for concurrent scraping
"""

import time
import asyncio
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import pandas as pd
from pathlib import Path
from datetime import datetime
import re  # for clean_price
from typing import Dict, List, Optional

from .logger import scraper_logger, log_scrape_result, log_task_start, log_task_complete


# Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PRICES_CSV = DATA_DIR / "prices.csv"
TIMEOUT = 15  # seconds


def get_chrome_driver() -> webdriver.Chrome:
    """Create and configure Chrome WebDriver with automatic driver management"""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )

        # Use webdriver-manager to automatically download and manage ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(TIMEOUT)
        return driver
    except Exception as e:
        scraper_logger.error(f"Failed to create Chrome driver: {e}")
        raise


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


async def scrape_bookscouter(isbn: str) -> Dict:
    """
    Scrape book price from BookScouter

    Args:
        isbn: The ISBN to search for

    Returns:
        Dictionary with scraping results
    """
    result = {
        "isbn": isbn,
        "source": "BookScouter",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }    driver = None
    try:
        url = f"https://bookscouter.com/book/{isbn}?type=buy"
        result["url"] = url

        # Run the synchronous scraping operation in a thread
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            scraping_result = await loop.run_in_executor(executor, _scrape_bookscouter_sync, isbn, url)
            result.update(scraping_result)

    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping BookScouter for ISBN {isbn}: {e}")

    log_scrape_result(scraper_logger, isbn, "BookScouter", result["success"], result["price"], result["notes"])
    return result


def _scrape_bookscouter_sync(isbn: str, url: str) -> Dict:
    """Synchronous helper function for BookScouter scraping"""
    result_update = {
        "price": None,
        "title": None,
        "notes": "",
        "success": False,
    }

    driver = None
    try:
        driver = get_chrome_driver()
        scraper_logger.info(f"Scraping BookScouter for ISBN: {isbn}")

        driver.get(url)

        # Wait for page to load
        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Try to find book title
        try:
            title_element = driver.find_element(By.CSS_SELECTOR, "h1, .BookDetailsTitle_bdlrv61")
            result_update["title"] = title_element.text.strip()
        except NoSuchElementException:
            scraper_logger.warning(f"Could not find title for ISBN {isbn} on BookScouter")

        # Try to find the lowest price
        try:
            # Look for price elements (BookScouter typically shows prices in a table)
            price_elements = driver.find_elements(
                By.CSS_SELECTOR,
                "[class^='CellSectionValue'], [class*='CellSectionValue']",
            )

            prices = []
            for element in price_elements:
                price_text = element.text.strip()
                price_value = clean_price(price_text)
                if price_value and price_value > 0:
                    prices.append(price_value)

            if prices:
                result_update["price"] = min(prices)  # Get lowest selling price
                result_update["success"] = True
                result_update["notes"] = f"Found {len(prices)} prices, showing lowest: ${result_update['price']:.2f}"
            else:
                result_update["notes"] = "No valid prices found"

        except NoSuchElementException:
            result_update["notes"] = "Price elements not found"

    except TimeoutException:
        result_update["notes"] = "Page load timeout"
        scraper_logger.error(f"Timeout scraping BookScouter for ISBN {isbn}")
    except WebDriverException as e:
        result_update["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping BookScouter for ISBN {isbn}: {e}")
    except Exception as e:
        result_update["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping BookScouter for ISBN {isbn}: {e}")
    finally:
        if driver:
            driver.quit()

    return result_update


async def scrape_christianbook(isbn: str) -> Dict:    """
    Scrape book price from Christianbook.com

    Args:
        isbn: The ISBN to search for

    Returns:
        Dictionary with scraping results
    """
    result = {
        "isbn": isbn,
        "source": "Christianbook",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    try:
        # Christianbook search URL
        search_url = f"https://www.christianbook.com/apps/search?Ntt={isbn}&Ntk=keywords&action=Search&Ne=0&event=BRSRCG%7CPSEN&nav_search=1&cms=1&ps_exit=RETURN%7Clegacy&ps_domain=www"
        result["url"] = search_url

        # Run the synchronous scraping operation in a thread
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            scraping_result = await loop.run_in_executor(executor, _scrape_christianbook_sync, isbn, search_url)
            result.update(scraping_result)

    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping Christianbook for ISBN {isbn}: {e}")

    log_scrape_result(scraper_logger, isbn, "Christianbook", result["success"], result["price"], result["notes"])
    return result


def _scrape_christianbook_sync(isbn: str, search_url: str) -> Dict:
    """Synchronous helper function for Christianbook scraping"""
    result_update = {
        "price": None,
        "title": None,
        "url": search_url,
        "notes": "",
        "success": False,
    }

    driver = None
    try:
        driver = get_chrome_driver()
        scraper_logger.info(f"Scraping Christianbook for ISBN: {isbn}")

        driver.get(search_url)

        # Wait for search results
        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Look for the first search result
        try:
            # Find product title
            title_selectors = [".CB-ProductListItem-Title"]

            title_element = None
            for selector in title_selectors:
                try:
                    title_element = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if title_element:
                result_update["title"] = title_element.text.strip()
                # Update URL to specific product page
                result_update["url"] = title_element.get_attribute("href")

            # Find price
            price_selectors = [
                ".price .sale-price",
                ".price .our-price",
                ".CBD-ProductDetailActionPrice",
                ".CBD-ProductDetailActionPrice span .sr-only",
                ".sale-price",
                ".our-price",
                "[class*='price']",
            ]

            price_element = None
            for selector in price_selectors:
                try:
                    price_element = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if price_element:
                price_text = price_element.text.strip()
                price_value = clean_price(price_text)
                if price_value and price_value > 0:
                    result_update["price"] = price_value
                    result_update["success"] = True
                    result_update["notes"] = "Found price in search results"
                else:
                    result_update["notes"] = f"Invalid price format: {price_text}"
            else:
                result_update["notes"] = "No price element found"

        except NoSuchElementException:
            result_update["notes"] = "No search results found"

    except TimeoutException:
        result_update["notes"] = "Page load timeout"
        scraper_logger.error(f"Timeout scraping Christianbook for ISBN {isbn}")
    except WebDriverException as e:
        result_update["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping Christianbook for ISBN {isbn}: {e}")
    except Exception as e:
        result_update["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping Christianbook for ISBN {isbn}: {e}")
    finally:
        if driver:
            driver.quit()

    return result_update


async def scrape_rainbowresource(isbn: str) -> Dict:
    """
    Scrape book price from RainbowResource.com

    Args:
        isbn: The ISBN to search for

    Returns:
        Dictionary with scraping results
    """
    result = {
        "isbn": isbn,
        "source": "RainbowResource",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    driver = None
    try:
        # RainbowResource search URL
        search_url = f"https://www.rainbowresource.com/catalogsearch/result?q={isbn}"
        result["url"] = search_url

        driver = get_chrome_driver()
        scraper_logger.info(f"Scraping RainbowResource for ISBN: {isbn}")

        driver.get(search_url)

        # Wait for search results
        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Look for search results
        try:
            # Find product title
            title_selectors = [
                ".hawk-results__item-name",
            ]

            title_element = None
            for selector in title_selectors:
                try:
                    title_element = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if title_element:
                result["title"] = title_element.text.strip()
                # Update URL to specific product page if available
                href = title_element.get_attribute("href")
                if href:
                    result["url"] = href

            # Find price
            price_selectors = [".special-price", "[class*='price']"]

            price_element = None
            for selector in price_selectors:
                try:
                    price_element = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if price_element:
                price_text = price_element.text.strip()
                price_value = clean_price(price_text)
                if price_value and price_value > 0:
                    result["price"] = price_value
                    result["success"] = True
                    result["notes"] = "Found price in search results"
                else:
                    result["notes"] = f"Invalid price format: {price_text}"
            else:
                result["notes"] = "No price element found"

        except NoSuchElementException:
            result["notes"] = "No search results found"

    except TimeoutException:
        result["notes"] = "Page load timeout"
        scraper_logger.error(f"Timeout scraping RainbowResource for ISBN {isbn}")
    except WebDriverException as e:
        result["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping RainbowResource for ISBN {isbn}: {e}")
    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping RainbowResource for ISBN {isbn}: {e}")
    finally:
        if driver:
            driver.quit()

    log_scrape_result(scraper_logger, isbn, "RainbowResource", result["success"], result["price"], result["notes"])
    return result


def scrape_camelcamelcamel(isbn: str) -> Dict:
    """
    Scrape Amazon price history from CamelCamelCamel
    Note: This gets the current Amazon price, not historical data

    Args:
        isbn: The ISBN to search for

    Returns:
        Dictionary with scraping results
    """
    result = {
        "isbn": isbn,
        "source": "CamelCamelCamel",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    driver = None
    try:
        # CamelCamelCamel search URL
        search_url = f"https://camelcamelcamel.com/search?sq={isbn}"
        result["url"] = search_url

        driver = get_chrome_driver()
        scraper_logger.info(f"Scraping CamelCamelCamel for ISBN: {isbn}")

        driver.get(search_url)

        # Wait for search results
        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Look for search results
        try:
            # Find first search result
            search_results = driver.find_elements(By.CSS_SELECTOR, ".search_item, .product")

            if search_results:
                first_result = search_results[0]

                # Get title
                try:
                    title_element = first_result.find_element(By.CSS_SELECTOR, "a")
                    result["title"] = title_element.text.strip()
                    result["url"] = title_element.get_attribute("href")
                except NoSuchElementException:
                    pass

                # Get current Amazon price
                try:
                    price_element = first_result.find_element(
                        By.CSS_SELECTOR, ".price, .amazon_price, [class*='price']"
                    )
                    price_text = price_element.text.strip()
                    price_value = clean_price(price_text)
                    if price_value and price_value > 0:
                        result["price"] = price_value
                        result["success"] = True
                        result["notes"] = "Current Amazon price from CamelCamelCamel"
                    else:
                        result["notes"] = f"Invalid price format: {price_text}"
                except NoSuchElementException:
                    result["notes"] = "No price found in search result"
            else:
                result["notes"] = "No search results found"

        except NoSuchElementException:
            result["notes"] = "No search results container found"

    except TimeoutException:
        result["notes"] = "Page load timeout"
        scraper_logger.error(f"Timeout scraping CamelCamelCamel for ISBN {isbn}")
    except WebDriverException as e:
        result["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping CamelCamelCamel for ISBN {isbn}: {e}")
    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping CamelCamelCamel for ISBN {isbn}: {e}")
    finally:
        if driver:
            driver.quit()

    log_scrape_result(scraper_logger, isbn, "CamelCamelCamel", result["success"], result["price"], result["notes"])
    return result


def scrape_all_sources(isbn: str) -> List[Dict]:
    """
    Scrape an ISBN from all sources

    Args:
        isbn: The ISBN to scrape

    Returns:
        List of result dictionaries from all sources
    """
    log_task_start(scraper_logger, f"Scraping all sources for ISBN {isbn}")
    start_time = time.time()

    sources = [scrape_bookscouter, scrape_christianbook, scrape_rainbowresource]  # , scrape_camelcamelcamel]

    results = []
    for scraper_func in sources:
        try:
            result = scraper_func(isbn)
            results.append(result)
            # Small delay between requests to be respectful
            time.sleep(2)
        except Exception as e:
            scraper_logger.error(f"Error in {scraper_func.__name__} for ISBN {isbn}: {e}")
            # Add a failed result
            results.append(
                {
                    "isbn": isbn,
                    "source": scraper_func.__name__.replace("scrape_", "").title(),
                    "price": None,
                    "title": None,
                    "url": None,
                    "notes": f"Scraper function failed: {str(e)}",
                    "success": False,
                }
            )

    end_time = time.time()
    duration = end_time - start_time

    successful_scrapes = len([r for r in results if r["success"]])
    log_task_complete(scraper_logger, f"Scraping all sources for ISBN {isbn}", duration)
    scraper_logger.info(f"Completed scraping ISBN {isbn}: {successful_scrapes}/{len(sources)} sources successful")

    return results


def save_results_to_csv(results: List[Dict]):
    """
    Save scraping results to CSV file

    Args:
        results: List of scraping result dictionaries
    """
    if not results:
        scraper_logger.warning("No results to save")
        return

    try:
        # Ensure data directory exists
        DATA_DIR.mkdir(exist_ok=True)

        # Add timestamp to results
        timestamp = datetime.now().isoformat()
        for result in results:
            result["timestamp"] = timestamp

        # Convert to DataFrame
        new_df = pd.DataFrame(results)

        # Load existing data if it exists
        if PRICES_CSV.exists():
            existing_df = pd.read_csv(PRICES_CSV)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        # Save to CSV
        combined_df.to_csv(PRICES_CSV, index=False)

        scraper_logger.info(f"Saved {len(results)} new price records to {PRICES_CSV}")

    except Exception as e:
        scraper_logger.error(f"Error saving results to CSV: {e}")


def load_isbns_from_file(filepath: str = None) -> dict[str, dict]:
    """
    Load ISBNs from a text file

    Args:
        filepath: Path to the ISBNs file (default: isbns.json in base directory)

    Returns:
        List of ISBNs
    """
    if filepath is None:
        filepath = BASE_DIR / "isbns.json"

    try:
        with open(filepath, "r") as f:
            isbns = json.load(f)

        scraper_logger.info(f"Loaded {len(list(isbns.keys()))} ISBNs from {filepath}")
        return isbns

    except FileNotFoundError:
        scraper_logger.warning(f"ISBNs file not found: {filepath}")
        return {}
    except Exception as e:
        scraper_logger.error(f"Error loading ISBNs from file: {e}")
        return {}


def scrape_all_isbns(isbn_file: str = None) -> None:
    """
    Scrape all ISBNs from file across all sources

    Args:
        isbn_file: Path to ISBNs file (optional)
    """
    log_task_start(scraper_logger, "Starting full ISBN scraping job")
    start_time = time.time()

    # Load ISBNs
    isbns = load_isbns_from_file(isbn_file)

    if not isbns:
        scraper_logger.warning("No ISBNs to scrape")
        return

    all_results = []

    for i, isbn in enumerate(isbns, 1):
        scraper_logger.info(f"Processing ISBN {i}/{len(isbns)}: {isbn}")

        # Scrape all sources for this ISBN
        isbn_results = scrape_all_sources(isbn)
        all_results.extend(isbn_results)

        # Save progress after each ISBN (in case of crash)
        if isbn_results:
            save_results_to_csv(isbn_results)

    end_time = time.time()
    duration = end_time - start_time

    successful_results = len([r for r in all_results if r["success"]])
    total_attempts = len(all_results)

    log_task_complete(scraper_logger, "Full ISBN scraping job", duration)
    scraper_logger.info(f"Scraping completed: {successful_results}/{total_attempts} successful scrapes")


if __name__ == "__main__":
    # Test the scrapers
    test_isbn = "9780134685991"  # Effective Java

    print("Testing scraper functions...")

    # Test individual scrapers
    print("\n1. Testing BookScouter...")
    result = scrape_bookscouter(test_isbn)
    print(f"   Result: {result}")

    print("\n2. Testing Christianbook...")
    result = scrape_christianbook(test_isbn)
    print(f"   Result: {result}")

    print("\n3. Testing RainbowResource...")
    result = scrape_rainbowresource(test_isbn)
    print(f"   Result: {result}")

    # print("\n4. Testing CamelCamelCamel...")
    # result = scrape_camelcamelcamel(test_isbn)
    # print(f"   Result: {result}")

    print("\n5. Testing all sources...")
    all_results = scrape_all_sources(test_isbn)
    save_results_to_csv(all_results)
    print(f"   Saved {len(all_results)} results to CSV")
