"""
Book Price Tracker - Google Books API Integration
Handles fetching book metadata from Google Books API (free, no API key required)
"""

import requests
import logging
from typing import Dict, Optional, List
from pathlib import Path
import urllib.parse

# Setup logging
logger = logging.getLogger(__name__)

# Google Books API Configuration
GOOGLE_BOOKS_BASE_URL = "https://www.googleapis.com/books/v1"


class GoogleBooksAPI:
    """Google Books API client for fetching book metadata"""

    def __init__(self):
        """
        Initialize Google Books API client
        No API key required for basic operations
        """
        self.base_url = GOOGLE_BOOKS_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BookPriceTracker/1.0"})

    def is_available(self) -> bool:
        """Check if Google Books API is available (always True as no key required)"""
        return True

    def fetch_book_metadata(self, isbn: str) -> Dict:
        """
        Fetch book metadata from Google Books API

        Args:
            isbn: ISBN-10 or ISBN-13

        Returns:
            Dictionary with book metadata or error information
        """
        result = {
            "isbn_input": isbn,
            "isbn13": None,
            "isbn10": None,
            "title": None,
            "authors": [],
            "publisher": None,
            "year": None,
            "success": False,
            "error": None,
        }

        # Clean ISBN (remove dashes, spaces)
        clean_isbn = isbn.replace("-", "").replace(" ", "")

        try:
            # Search by ISBN using Google Books API
            query = f"isbn:{clean_isbn}"
            url = f"{self.base_url}/volumes"
            params = {"q": query, "maxResults": 1}

            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if data.get("totalItems", 0) > 0:
                    # Get the first book from results
                    book = data["items"][0]["volumeInfo"]

                    # Extract metadata
                    result["title"] = book.get("title")
                    result["authors"] = book.get("authors", [])
                    result["publisher"] = book.get("publisher")

                    # Extract publication year
                    published_date = book.get("publishedDate", "")
                    if published_date:
                        result["year"] = published_date.split("-")[0]  # Get year from date

                    # Extract ISBNs from industryIdentifiers
                    identifiers = book.get("industryIdentifiers", [])
                    for identifier in identifiers:
                        if identifier.get("type") == "ISBN_13":
                            result["isbn13"] = identifier.get("identifier")
                        elif identifier.get("type") == "ISBN_10":
                            result["isbn10"] = identifier.get("identifier")

                    # If we don't have both ISBN formats, try to convert
                    if not result["isbn13"] and result["isbn10"]:
                        result["isbn13"] = self._convert_isbn10_to_isbn13(result["isbn10"])
                    elif not result["isbn10"] and result["isbn13"]:
                        result["isbn10"] = self._convert_isbn13_to_isbn10(result["isbn13"])

                    # If we still don't have ISBNs, use the input ISBN
                    if not result["isbn13"] and not result["isbn10"]:
                        if len(clean_isbn) == 13:
                            result["isbn13"] = clean_isbn
                            result["isbn10"] = self._convert_isbn13_to_isbn10(clean_isbn)
                        elif len(clean_isbn) == 10:
                            result["isbn10"] = clean_isbn
                            result["isbn13"] = self._convert_isbn10_to_isbn13(clean_isbn)

                    result["success"] = True
                    logger.info(f"Successfully fetched metadata for ISBN {isbn}: {result['title']}")

                else:
                    result["error"] = "Book not found in Google Books"
                    logger.warning(f"Book not found in Google Books for ISBN {isbn}")

            elif response.status_code == 429:
                result["error"] = "Google Books API rate limit exceeded"
                logger.warning("Google Books API rate limit exceeded")

            else:
                result["error"] = f"Google Books API error: {response.status_code}"
                logger.error(f"Google Books API error {response.status_code}: {response.text}")

        except requests.RequestException as e:
            result["error"] = f"Network error: {str(e)}"
            logger.error(f"Network error fetching Google Books data for {isbn}: {e}")

        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error fetching Google Books data for {isbn}: {e}")

        return result

    def _convert_isbn10_to_isbn13(self, isbn10: str) -> Optional[str]:
        """Convert ISBN-10 to ISBN-13"""
        try:
            if not isbn10 or len(isbn10) != 10:
                return None

            # Remove check digit and add 978 prefix
            isbn13_prefix = "978" + isbn10[:-1]

            # Calculate check digit for ISBN-13
            check_sum = sum((3 if i % 2 else 1) * int(d) for i, d in enumerate(isbn13_prefix))
            check_digit = (10 - (check_sum % 10)) % 10

            return isbn13_prefix + str(check_digit)
        except Exception:
            return None

    def _convert_isbn13_to_isbn10(self, isbn13: str) -> Optional[str]:
        """Convert ISBN-13 to ISBN-10"""
        try:
            if not isbn13 or len(isbn13) != 13 or not isbn13.startswith("978"):
                return None

            # Extract digits after 978 prefix, excluding check digit
            isbn10_digits = isbn13[3:12]

            # Calculate check digit for ISBN-10
            check_sum = sum((10 - i) * int(d) for i, d in enumerate(isbn10_digits))
            check_digit = (11 - (check_sum % 11)) % 11
            check_digit = "X" if check_digit == 10 else str(check_digit)

            return isbn10_digits + check_digit
        except Exception:
            return None

    def normalize_isbn(self, isbn: str) -> Dict:
        """
        Normalize ISBN to both ISBN-10 and ISBN-13 formats
        Uses Google Books if available to get both formats

        Args:
            isbn: ISBN in any format

        Returns:
            Dictionary with normalized ISBN data
        """
        result = {"isbn_input": isbn, "isbn13": None, "isbn10": None, "success": False}

        # Clean ISBN
        clean_isbn = isbn.replace("-", "").replace(" ", "")

        # Basic validation
        if not clean_isbn.isdigit() or len(clean_isbn) not in [10, 13]:
            result["error"] = "Invalid ISBN format"
            return result

        # Try to get both formats from Google Books
        metadata = self.fetch_book_metadata(isbn)
        if metadata["success"]:
            result["isbn13"] = metadata["isbn13"]
            result["isbn10"] = metadata["isbn10"]
            result["success"] = True
            return result

        # Fallback to basic conversion
        if len(clean_isbn) == 13:
            result["isbn13"] = clean_isbn
            result["isbn10"] = self._convert_isbn13_to_isbn10(clean_isbn)
            result["success"] = True

        elif len(clean_isbn) == 10:
            result["isbn10"] = clean_isbn
            result["isbn13"] = self._convert_isbn10_to_isbn13(clean_isbn)
            result["success"] = True

        return result

    def search_by_title_and_author(self, title: str, author: str = None, max_results: int = 5) -> List[Dict]:
        """
        Search for books by title and (optionally) author

        Args:
            title: Book title to search for
            author: Author name to search for (optional, but recommended)
            max_results: Maximum number of results to return

        Returns:
            List of dictionaries with book metadata
        """
        results = []
        try:
            # Build query string
            query = f"intitle:{title}"
            if author:
                query += f"+inauthor:{author}"
            url = f"{self.base_url}/volumes"
            params = {"q": query, "maxResults": max_results}
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", []):
                    book = item["volumeInfo"]
                    # Extract ISBNs
                    isbn13 = None
                    isbn10 = None
                    identifiers = book.get("industryIdentifiers", [])
                    for identifier in identifiers:
                        if identifier.get("type") == "ISBN_13":
                            isbn13 = identifier.get("identifier")
                        elif identifier.get("type") == "ISBN_10":
                            isbn10 = identifier.get("identifier")
                        else:
                            print(f"Unknown identifier type: {identifier.get('type')}: {identifier.get('identifier')}")
                    result = {
                        "title": book.get("title"),
                        "authors": book.get("authors", []),
                        "publisher": book.get("publisher"),
                        "year": book.get("publishedDate", "").split("-")[0] if book.get("publishedDate") else None,
                        "isbn13": isbn13,
                        "isbn10": isbn10,
                    }
                    results.append(result)
        except Exception as e:
            logger.error(f"Error searching by title and author '{title}' '{author}': {e}")
        return results

    # For backward compatibility, keep the old name as an alias
    def search_by_title(self, title: str, max_results: int = 5) -> List[Dict]:
        return self.search_by_title_and_author(title, None, max_results)


def get_book_metadata(isbn: str) -> Dict:
    """
    Convenience function to get book metadata

    Args:
        isbn: ISBN to lookup

    Returns:
        Dictionary with book metadata
    """
    api = GoogleBooksAPI()
    return api.fetch_book_metadata(isbn)


def normalize_isbn(isbn: str) -> Dict:
    """
    Convenience function to normalize ISBN

    Args:
        isbn: ISBN to normalize

    Returns:
        Dictionary with normalized ISBN data
    """
    api = GoogleBooksAPI()
    return api.normalize_isbn(isbn)


def search_books_by_title(title: str, max_results: int = 5) -> List[Dict]:
    """
    Convenience function to search books by title

    Args:
        title: Book title to search for
        max_results: Maximum number of results to return

    Returns:
        List of dictionaries with book metadata
    """
    api = GoogleBooksAPI()
    return api.search_by_title(title, max_results)


if __name__ == "__main__":
    # Test the Google Books API
    test_isbn = "9780134685991"  # Effective Java

    print(f"Testing Google Books API with ISBN: {test_isbn}")
    print("=" * 50)

    # Test metadata fetching
    metadata = get_book_metadata(test_isbn)
    print("Metadata result:")
    for key, value in metadata.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 50)

    # Test ISBN normalization
    isbn_data = normalize_isbn(test_isbn)
    print("ISBN normalization result:")
    for key, value in isbn_data.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 50)

    # Test title search
    if metadata.get("title"):
        search_results = search_books_by_title(metadata["title"], 3)
        print(f"Search results for '{metadata['title']}':")
        for i, result in enumerate(search_results, 1):
            print(f"  {i}. {result['title']} by {', '.join(result.get('authors', []))}")
            print(f"     ISBN-13: {result.get('isbn13', 'N/A')}, ISBN-10: {result.get('isbn10', 'N/A')}")
