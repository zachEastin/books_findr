"""
Book Price Tracker - Async Web Scraping Module
Handles scraping from BookScouter, Christianbook, RainbowResource, and CamelCamelCamel
Uses asyncio for concurrent scraping to improve performance
Integrates with ISBNdb API for enhanced search capabilities
"""

import time
import asyncio
import urllib.parse
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
from typing import Optional

from .logger import scraper_logger, log_scrape_result, log_task_start, log_task_complete
import json


# Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PRICES_CSV = DATA_DIR / "prices.csv"
TIMEOUT = 15  # seconds
MAX_CONCURRENT_SCRAPERS = 3  # Limit concurrent scrapers to be respectful


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


def get_search_strategies(isbn_data: dict) -> list[tuple[str, str]]:
    """
    Get search strategies for an ISBN in order of preference

    Args:
        isbn: The original ISBN metadata dictionary

    Returns:
        List of (search_term, strategy_name) tuples in order of preference
    """
    strategies = []

    try:
        # Strategy 1: Use ISBN-13 if available
        isbn_13 = isbn_data.get("isbn13")
        if isbn_13:
            strategies.append((isbn_13, "ISBN-13 from metadata"))
            scraper_logger.info(f"Found ISBN-13 {isbn_13}")

        # Strategy 2: Use title if available
        title = isbn_data.get("title")
        if title:
            # Clean title for search (remove subtitle after colon, etc.)
            clean_title = title.split(":")[0].strip()
            strategies.append((clean_title, "title from metadata"))
            scraper_logger.info(f"Found title '{clean_title}' for {isbn_data.get('isbn_13', 'unknown')}")
        else:
            scraper_logger.warning(f"No title found in metadata for ISBN {isbn_data.get('isbn_13', 'unknown')}")

    except Exception as e:
        scraper_logger.warning(f"Error getting search strategies for {isbn_data.get('isbn_13', 'unknown')}: {e}")

    return strategies


def _scrape_bookscouter_sync(search_term: str, url: str) -> dict:
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
        scraper_logger.info(f"Scraping BookScouter for term: {search_term}")

        driver.get(url)

        # Wait for page to load
        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Wait 5 seconds for dynamic content to load
        time.sleep(5)

        # Try to find book title
        try:
            title_element = driver.find_element(By.CSS_SELECTOR, "h1, .BookDetailsTitle_bdlrv61")
            result_update["title"] = title_element.text.strip()
        except NoSuchElementException:
            scraper_logger.warning(f"Could not find title for term `{search_term}` on BookScouter")

        # Try to find the lowest price
        try:
            # Look for price elements (BookScouter typically shows prices in a table)
            price_elements = driver.find_elements(
                By.CSS_SELECTOR,
                "[class^='BestVendorPrice'], [class*='BestVendorPrice']",
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
        scraper_logger.error(f"Timeout scraping BookScouter for term {search_term}")
    except WebDriverException as e:
        result_update["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping BookScouter for term {search_term}: {e}")
    except Exception as e:
        result_update["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping BookScouter for term {search_term}: {e}")
    finally:
        if driver:
            driver.quit()

    return result_update


def _scrape_christianbook_sync(search_term: str, search_url: str) -> dict:
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
        scraper_logger.info(f"Scraping Christianbook for term: {search_term}")

        driver.get(search_url)

        # Wait for search results
        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Wait 5 seconds for dynamic content to load
        time.sleep(5)

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
                href = title_element.get_attribute("href")
                if href:
                    result_update["url"] = href

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
        scraper_logger.error(f"Timeout scraping Christianbook for term {search_term}")
    except WebDriverException as e:
        result_update["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping Christianbook for term {search_term}: {e}")
    except Exception as e:
        result_update["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping Christianbook for term {search_term}: {e}")
    finally:
        if driver:
            driver.quit()

    return result_update


def _scrape_rainbowresource_sync(search_term: str, search_url: str) -> dict:
    """Synchronous helper function for RainbowResource scraping"""
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
        scraper_logger.info(f"Scraping RainbowResource for term: {search_term}")

        driver.get(search_url)

        # Wait for search results
        WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Wait 5 seconds for dynamic content to load
        time.sleep(5)

        # Look for search results
        try:
            # Find product title
            title_selectors = [".hawk-results__item-name"]

            title_element = None
            for selector in title_selectors:
                try:
                    title_element = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if title_element:
                result_update["title"] = title_element.text.strip()
                # Update URL to specific product page if available
                href = title_element.get_attribute("href")
                if href:
                    result_update["url"] = href

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
        scraper_logger.error(f"Timeout scraping RainbowResource for term {search_term}")
    except WebDriverException as e:
        result_update["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping RainbowResource for term {search_term}: {e}")
    except Exception as e:
        result_update["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping RainbowResource for term {search_term}: {e}")
    finally:
        if driver:
            driver.quit()

    return result_update


def _scrape_camelcamelcamel_sync(isbn: str, search_url: str) -> dict:
    """Synchronous helper function for CamelCamelCamel scraping"""
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
                    result_update["title"] = title_element.text.strip()
                    href = title_element.get_attribute("href")
                    if href:
                        result_update["url"] = href
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
                        result_update["price"] = price_value
                        result_update["success"] = True
                        result_update["notes"] = "Current Amazon price from CamelCamelCamel"
                    else:
                        result_update["notes"] = f"Invalid price format: {price_text}"
                except NoSuchElementException:
                    result_update["notes"] = "No price found in search result"
            else:
                result_update["notes"] = "No search results found"

        except NoSuchElementException:
            result_update["notes"] = "No search results container found"

    except TimeoutException:
        result_update["notes"] = "Page load timeout"
        scraper_logger.error(f"Timeout scraping CamelCamelCamel for ISBN {isbn}")
    except WebDriverException as e:
        result_update["notes"] = f"WebDriver error: {str(e)}"
        scraper_logger.error(f"WebDriver error scraping CamelCamelCamel for ISBN {isbn}: {e}")
    except Exception as e:
        result_update["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(f"Unexpected error scraping CamelCamelCamel for ISBN {isbn}: {e}")
    finally:
        if driver:
            driver.quit()

    return result_update


# Async scraper functions
async def scrape_bookscouter_async(isbn_data: dict) -> dict:
    """
    Async scrape book price from BookScouter with enhanced search strategies

    Args:
        isbn: The ISBN to search for

    Returns:
        dictionary with scraping results
    """
    result = {
        "isbn": isbn_data.get("isbn13"),
        "source": "BookScouter",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    try:
        # Get search strategies in order of preference
        search_strategies = get_search_strategies(isbn_data)
        scraper_logger.info(
            f"BookScouter: Trying {len(search_strategies)} search strategies for {isbn_data.get('title', isbn_data.get('isbn13', 'unknown'))}"
        )

        # Try each search strategy until we find results
        for search_term, strategy_name in search_strategies:
            try:
                # BookScouter uses direct ISBN lookup in URL
                url = f"https://bookscouter.com/book/{search_term}?type=buy"
                result["url"] = url

                scraper_logger.info(f"BookScouter: Trying {strategy_name} with term '{search_term}'")

                scraping_result = _scrape_bookscouter_sync(search_term, url)

                if scraping_result.get("success"):
                    result.update(scraping_result)
                    result["notes"] = f"Found using {strategy_name}: {result['notes']}"
                    scraper_logger.info(f"BookScouter: Success with {strategy_name}")
                    break
                else:
                    scraper_logger.info(
                        f"BookScouter: No results with {strategy_name} for term {search_term} and url {url}"
                    )

            except Exception as e:
                scraper_logger.warning(f"BookScouter: Error with {strategy_name}: {e}")
                continue

        if not result["success"]:
            result["notes"] = f"No results found with any search strategy (tried {len(search_strategies)} methods)"

    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(
            f"Unexpected error scraping BookScouter for ISBN {isbn_data.get('isbn13', 'unknown')}: {e}"
        )

    log_scrape_result(
        scraper_logger,
        isbn_data.get("isbn13", "unknown"),
        "BookScouter",
        result["success"],
        result["price"],
        result["notes"],
    )
    return result


async def scrape_christianbook_async(isbn_data: dict) -> dict:
    """
    Async scrape book price from Christianbook.com with enhanced search strategies

    Args:
        isbn: The ISBN metadata to search for

    Returns:
        dictionary with scraping results
    """
    result = {
        "isbn": isbn_data.get("isbn13", "unknown"),
        "source": "Christianbook",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    try:
        # Get search strategies in order of preference
        search_strategies = get_search_strategies(isbn_data)
        scraper_logger.info(
            f"Christianbook: Trying {len(search_strategies)} search strategies for {isbn_data.get('title', 'unknown')}"
        )

        # Try each search strategy until we find results
        for search_term, strategy_name in search_strategies:
            try:  # Christianbook search URL with URL encoding
                encoded_term = urllib.parse.quote(search_term)
                search_url = f"https://www.christianbook.com/apps/search?Ntt={encoded_term}&Ntk=keywords&action=Search&Ne=0&event=BRSRCG%7CPSEN&nav_search=1&cms=1&ps_exit=RETURN%7Clegacy&ps_domain=www"
                result["url"] = search_url

                scraper_logger.info(f"Christianbook: Trying {strategy_name} with term '{search_term}'")

                scraping_result = _scrape_christianbook_sync(search_term, search_url)

                if scraping_result.get("success"):
                    result.update(scraping_result)
                    result["notes"] = f"Found using {strategy_name}: {result['notes']}"
                    scraper_logger.info(f"Christianbook: Success with {strategy_name}")
                    break
                else:
                    scraper_logger.info(
                        f"Christianbook: No results with {strategy_name} for term {search_term} and url {search_url}"
                    )

            except Exception as e:
                scraper_logger.warning(f"Christianbook: Error with {strategy_name}: {e}")
                continue

        if not result["success"]:
            result["notes"] = f"No results found with any search strategy (tried {len(search_strategies)} methods)"

    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(
            f"Unexpected error scraping Christianbook for ISBN {isbn_data.get('isbn13', 'unknown')}: {e}"
        )

    log_scrape_result(
        scraper_logger,
        isbn_data.get("isbn13", "unknown"),
        "Christianbook",
        result["success"],
        result["price"],
        result["notes"],
    )
    return result


async def scrape_rainbowresource_async(isbn_data: dict) -> dict:
    """
    Async scrape book price from RainbowResource.com with enhanced search strategies

    Args:
        isbn: The ISBN metadata to search for

    Returns:
        dictionary with scraping results
    """
    result = {
        "isbn": isbn_data.get("isbn13", "unknown"),
        "source": "RainbowResource",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    try:
        # Get search strategies in order of preference
        search_strategies = get_search_strategies(isbn_data)
        scraper_logger.info(
            f"RainbowResource: Trying {len(search_strategies)} search strategies for {isbn_data.get('title', 'unknown')}"
        )

        # Try each search strategy until we find results
        for search_term, strategy_name in search_strategies:
            try:  # RainbowResource search URL with URL encoding
                encoded_term = urllib.parse.quote(search_term)
                search_url = f"https://www.rainbowresource.com/catalogsearch/result?q={encoded_term}"
                result["url"] = search_url

                scraper_logger.info(f"RainbowResource: Trying {strategy_name} with term '{search_term}'")

                scraping_result = _scrape_rainbowresource_sync(search_term, search_url)

                if scraping_result.get("success"):
                    result.update(scraping_result)
                    result["notes"] = f"Found using {strategy_name}: {result['notes']}"
                    scraper_logger.info(f"RainbowResource: Success with {strategy_name}")
                    break
                else:
                    scraper_logger.info(
                        f"RainbowResource: No results with {strategy_name} for term {search_term} and url {search_url}"
                    )

            except Exception as e:
                scraper_logger.warning(f"RainbowResource: Error with {strategy_name}: {e}")
                continue

        if not result["success"]:
            result["notes"] = f"No results found with any search strategy (tried {len(search_strategies)} methods)"

    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(
            f"Unexpected error scraping RainbowResource for ISBN {isbn_data.get('isbn13', 'unknown')}: {e}"
        )

    log_scrape_result(
        scraper_logger,
        isbn_data.get("isbn13", "unknown"),
        "RainbowResource",
        result["success"],
        result["price"],
        result["notes"],
    )
    return result


async def scrape_camelcamelcamel_async(isbn_data: dict) -> dict:
    """
    Async scrape Amazon price history from CamelCamelCamel with enhanced search strategies
    Note: This gets the current Amazon price, not historical data

    Args:
        isbn: The ISBN metadata to search for

    Returns:
        dictionary with scraping results
    """
    result = {
        "isbn": isbn_data.get("isbn13", "unknown"),
        "source": "CamelCamelCamel",
        "price": None,
        "title": None,
        "url": None,
        "notes": "",
        "success": False,
    }

    try:
        # Get search strategies in order of preference
        search_strategies = get_search_strategies(isbn_data)
        scraper_logger.info(
            f"CamelCamelCamel: Trying {len(search_strategies)} search strategies for {isbn_data.get('title', 'unknown')}"
        )

        # Try each search strategy until we find results
        for search_term, strategy_name in search_strategies:
            try:  # CamelCamelCamel search URL with URL encoding
                encoded_term = urllib.parse.quote(search_term)
                search_url = f"https://camelcamelcamel.com/search?sq={encoded_term}"
                result["url"] = search_url

                scraper_logger.info(f"CamelCamelCamel: Trying {strategy_name} with term '{search_term}'")

                scraping_result = _scrape_camelcamelcamel_sync(search_term, search_url)

                if scraping_result.get("success"):
                    result.update(scraping_result)
                    result["notes"] = f"Found using {strategy_name}: {result['notes']}"
                    scraper_logger.info(f"CamelCamelCamel: Success with {strategy_name}")
                    break
                else:
                    scraper_logger.info(
                        f"CamelCamelCamel: No results with {strategy_name} for term {search_term} and url {search_url}"
                    )

            except Exception as e:
                scraper_logger.warning(f"CamelCamelCamel: Error with {strategy_name}: {e}")
                continue

        if not result["success"]:
            result["notes"] = f"No results found with any search strategy (tried {len(search_strategies)} methods)"

    except Exception as e:
        result["notes"] = f"Unexpected error: {str(e)}"
        scraper_logger.error(
            f"Unexpected error scraping CamelCamelCamel for ISBN {isbn_data.get('isbn13', 'unknown')}: {e}"
        )

    log_scrape_result(
        scraper_logger,
        isbn_data.get("isbn13", "unknown"),
        "CamelCamelCamel",
        result["success"],
        result["price"],
        result["notes"],
    )
    return result


async def scrape_all_sources_async(isbn: dict) -> list[dict]:
    """
    Async scrape an ISBN from all sources concurrently

    Args:
        isbn: The ISBN to scrape

    Returns:
        List of result dictionaries from all sources
    """
    log_task_start(scraper_logger, f"Async scraping all sources for ISBN {isbn.get('isbn13') or 'unknown'}")
    start_time = time.time()  # Create async tasks for all scrapers
    tasks = [
        scrape_bookscouter_async(isbn),
        scrape_christianbook_async(isbn),
        scrape_rainbowresource_async(isbn),
        # scrape_camelcamelcamel_async(isbn),  # Uncomment to include CamelCamelCamel
    ]

    try:
        # Run all scrapers concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle any exceptions
        processed_results = []
        source_names = ["BookScouter", "Christianbook", "RainbowResource"]  # , "CamelCamelCamel"]

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle exceptions from failed scrapers
                scraper_logger.error(f"Error in {source_names[i]} for ISBN {isbn}: {result}")
                processed_results.append(
                    {
                        "isbn": isbn,
                        "source": source_names[i],
                        "price": None,
                        "title": None,
                        "url": None,
                        "notes": f"Scraper function failed: {str(result)}",
                        "success": False,
                    }
                )
            else:
                processed_results.append(result)

        results = processed_results

    except Exception as e:
        scraper_logger.error(f"Unexpected error in scrape_all_sources for ISBN {isbn}: {e}")
        results = []

    end_time = time.time()
    duration = end_time - start_time

    successful_scrapes = len([r for r in results if r.get("success", False)])
    log_task_complete(
        scraper_logger, f"Async scraping all sources for ISBN {isbn.get('isbn13') or 'unknown'}", duration
    )
    scraper_logger.info(
        f"Completed async scraping ISBN {isbn.get('isbn13')}: {successful_scrapes}/{len(tasks)} sources successful"
    )

    return results


async def scrape_multiple_isbns(isbns: list[str], batch_size: int = MAX_CONCURRENT_SCRAPERS) -> list[dict]:
    """
    Async scrape multiple ISBNs with controlled concurrency

    Args:
        isbns: List of ISBNs to scrape
        batch_size: Maximum number of concurrent ISBN scraping operations

    Returns:
        List of all scraping results
    """
    log_task_start(scraper_logger, f"Starting async bulk scraping for {len(isbns)} ISBNs")
    start_time = time.time()

    all_results = []

    # Process ISBNs in batches to avoid overwhelming the sites
    for i in range(0, len(isbns), batch_size):
        batch = list(isbns.values())[i : i + batch_size]
        scraper_logger.info(f"Processing batch {i // batch_size + 1}: ISBNs {i + 1}-{min(i + batch_size, len(isbns))}")

        # Create tasks for this batch
        batch_tasks = [scrape_all_sources_async(isbn) for isbn in batch]

        try:
            # Run batch concurrently
            batch_results = await asyncio.gather(*batch_tasks)

            # Flatten results (each ISBN returns a list of results from different sources)
            for isbn_results in batch_results:
                all_results.extend(isbn_results)

            # Small delay between batches to be respectful to the sites
            if i + batch_size < len(isbns):
                await asyncio.sleep(2)

        except Exception as e:
            scraper_logger.error(f"Error processing batch {i // batch_size + 1}: {e}")

    end_time = time.time()
    duration = end_time - start_time

    successful_results = len([r for r in all_results if r.get("success", False)])
    log_task_complete(scraper_logger, f"Async bulk scraping for {len(isbns)} ISBNs", duration)
    scraper_logger.info(f"Async bulk scraping completed: {successful_results}/{len(all_results)} successful scrapes")

    return all_results


def save_results_to_csv(results: list[dict]):
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


async def scrape_all_isbns_async(isbn_file: str = None) -> None:
    """
    Async scrape all ISBNs from file across all sources with improved performance

    Args:
        isbn_file: Path to ISBNs file (optional)
    """
    log_task_start(scraper_logger, "Starting async full ISBN scraping job")
    start_time = time.time()

    # Load ISBNs
    isbns = load_isbns_from_file(isbn_file)

    if not isbns:
        scraper_logger.warning("No ISBNs to scrape")
        return

    # Scrape all ISBNs concurrently with controlled batching
    all_results = await scrape_multiple_isbns(isbns)

    # Save all results at once
    if all_results:
        save_results_to_csv(all_results)

    end_time = time.time()
    duration = end_time - start_time

    successful_results = len([r for r in all_results if r.get("success", False)])
    total_attempts = len(all_results)

    log_task_complete(scraper_logger, "Async full ISBN scraping job", duration)
    scraper_logger.info(f"Async scraping completed: {successful_results}/{total_attempts} successful scrapes")


# Remove the sync wrapper and make scrape_all_isbns async
scrape_all_isbns = scrape_all_isbns_async


# Sync wrapper functions for backward compatibility
def scrape_bookscouter_sync(isbn: str) -> dict:
    """Sync wrapper for scrape_bookscouter_async"""
    return asyncio.run(scrape_bookscouter_async(isbn))


def scrape_christianbook_sync(isbn: str) -> dict:
    """Sync wrapper for scrape_christianbook_async"""
    return asyncio.run(scrape_christianbook_async(isbn))


def scrape_rainbowresource_sync(isbn: str) -> dict:
    """Sync wrapper for scrape_rainbowresource_async"""
    return asyncio.run(scrape_rainbowresource_async(isbn))


def scrape_camelcamelcamel_sync(isbn: str) -> dict:
    """Sync wrapper for scrape_camelcamelcamel_async"""
    return asyncio.run(scrape_camelcamelcamel_async(isbn))


def scrape_all_sources_sync(isbn: dict) -> list[dict]:
    """
    Sync wrapper for scrape_all_sources_async - maintains backward compatibility

    Args:
        isbn: The ISBN to scrape

    Returns:
        List of result dictionaries from all sources
    """
    return asyncio.run(scrape_all_sources_async(isbn))


# Backward compatibility: Export sync versions under original names
scrape_bookscouter = scrape_bookscouter_sync
scrape_christianbook = scrape_christianbook_sync
scrape_rainbowresource = scrape_rainbowresource_sync
scrape_camelcamelcamel = scrape_camelcamelcamel_sync
scrape_all_sources = scrape_all_sources_sync


if __name__ == "__main__":
    # Test the async scrapers
    test_isbn = "9780134685991"  # Effective Java

    async def test_async_scrapers():
        print("Testing async scraper functions...")

        # Test individual scrapers        print("\n1. Testing async BookScouter...")
        result = await scrape_bookscouter_async(test_isbn)
        print(f"   Result: {result}")

        print("\n2. Testing async Christianbook...")
        result = await scrape_christianbook_async(test_isbn)
        print(f"   Result: {result}")

        print("\n3. Testing async RainbowResource...")
        result = await scrape_rainbowresource_async(test_isbn)
        print(f"   Result: {result}")

        print("\n4. Testing async all sources (concurrent)...")
        all_results = await scrape_all_sources_async(test_isbn)
        save_results_to_csv(all_results)
        print(f"   Saved {len(all_results)} results to CSV")

        print("\n5. Testing multiple ISBNs async...")
        test_isbns = [test_isbn, "9780132350884"]  # Add another test ISBN
        multiple_results = await scrape_multiple_isbns(test_isbns, batch_size=2)
        print(f"   Processed {len(test_isbns)} ISBNs, got {len(multiple_results)} total results")

    # Run the async test
    asyncio.run(test_async_scrapers())
