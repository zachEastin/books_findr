"""
Book Price Tracker - ISBNdb API Integration
Handles fetching book metadata from ISBNdb.com API
"""

import requests
import logging
from typing import Dict, Optional
from pathlib import Path

# Setup logging
logger = logging.getLogger(__name__)

# ISBNdb API Configuration
ISBNDB_BASE_URL = "https://api2.isbndb.com"
ISBNDB_API_KEY = None  # Will be set via environment variable or config


class ISBNdbAPI:
    """ISBNdb API client for fetching book metadata"""

    def __init__(self, api_key: str = None):
        """
        Initialize ISBNdb API client

        Args:
            api_key: ISBNdb API key. If None, will try to load from environment
        """
        self.api_key = api_key or self._load_api_key()
        self.base_url = ISBNDB_BASE_URL
        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update({"Authorization": self.api_key, "Content-Type": "application/json"})
        else:
            logger.warning("No ISBNdb API key found. Book metadata fetching will be disabled.")

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment variable or config file"""
        import os

        # Try environment variable first
        api_key = os.environ.get("ISBNDB_API_KEY")
        if api_key:
            return api_key

        # Try config file
        config_file = Path(__file__).parent.parent / "config.txt"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    for line in f:
                        if line.startswith("ISBNDB_API_KEY="):
                            return line.split("=", 1)[1].strip()
            except Exception as e:
                logger.error(f"Error reading config file: {e}")

        return None

    def is_available(self) -> bool:
        """Check if ISBNdb API is available (has API key)"""
        return self.api_key is not None

    def fetch_book_metadata(self, isbn: str) -> Dict:
        """
        Fetch book metadata from ISBNdb API

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

        if not self.is_available():
            result["error"] = "ISBNdb API key not configured"
            logger.warning("ISBNdb API key not available")
            return result

        # Clean ISBN (remove dashes, spaces)
        clean_isbn = isbn.replace("-", "").replace(" ", "")

        try:
            # Make API request
            url = f"{self.base_url}/book/{clean_isbn}"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                book = data.get("book", {})

                # Extract metadata
                result["title"] = book.get("title")
                result["isbn13"] = book.get("isbn13")
                result["isbn10"] = book.get("isbn")  # Note: ISBNdb uses 'isbn' for ISBN-10
                result["authors"] = book.get("authors", [])
                result["publisher"] = book.get("publisher")
                result["year"] = book.get("date_published", "").split("-")[0] if book.get("date_published") else None
                result["success"] = True

                logger.info(f"Successfully fetched metadata for ISBN {isbn}: {result['title']}")

            elif response.status_code == 404:
                result["error"] = "Book not found in ISBNdb"
                logger.warning(f"Book not found in ISBNdb for ISBN {isbn}")

            elif response.status_code == 401:
                result["error"] = "ISBNdb API authentication failed"
                logger.error("ISBNdb API authentication failed - check API key")

            elif response.status_code == 429:
                result["error"] = "ISBNdb API rate limit exceeded"
                logger.warning("ISBNdb API rate limit exceeded")

            else:
                result["error"] = f"ISBNdb API error: {response.status_code}"
                logger.error(f"ISBNdb API error {response.status_code}: {response.text}")

        except requests.RequestException as e:
            result["error"] = f"Network error: {str(e)}"
            logger.error(f"Network error fetching ISBNdb data for {isbn}: {e}")

        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error fetching ISBNdb data for {isbn}: {e}")

        return result

    def normalize_isbn(self, isbn: str) -> Dict:
        """
        Normalize ISBN to both ISBN-10 and ISBN-13 formats
        Uses ISBNdb if available, otherwise does basic conversion

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

        # If we have ISBNdb, use it to get both formats
        if self.is_available():
            metadata = self.fetch_book_metadata(isbn)
            if metadata["success"]:
                result["isbn13"] = metadata["isbn13"]
                result["isbn10"] = metadata["isbn10"]
                result["success"] = True
                return result

        # Fallback to basic conversion
        if len(clean_isbn) == 13:
            result["isbn13"] = clean_isbn
            # Convert ISBN-13 to ISBN-10 (basic conversion)
            if clean_isbn.startswith("978"):
                isbn10_digits = clean_isbn[3:12]
                # Calculate check digit for ISBN-10
                check_sum = sum((10 - i) * int(d) for i, d in enumerate(isbn10_digits))
                check_digit = (11 - (check_sum % 11)) % 11
                check_digit = "X" if check_digit == 10 else str(check_digit)
                result["isbn10"] = isbn10_digits + check_digit
                result["success"] = True

        elif len(clean_isbn) == 10:
            result["isbn10"] = clean_isbn
            # Convert ISBN-10 to ISBN-13
            isbn13_prefix = "978" + clean_isbn[:-1]
            # Calculate check digit for ISBN-13
            check_sum = sum((3 if i % 2 else 1) * int(d) for i, d in enumerate(isbn13_prefix))
            check_digit = (10 - (check_sum % 10)) % 10
            result["isbn13"] = isbn13_prefix + str(check_digit)
            result["success"] = True

        return result


def get_book_metadata(isbn: str) -> Dict:
    """
    Convenience function to get book metadata

    Args:
        isbn: ISBN to lookup

    Returns:
        Dictionary with book metadata
    """
    api = ISBNdbAPI()
    return api.fetch_book_metadata(isbn)


def normalize_isbn(isbn: str) -> Dict:
    """
    Convenience function to normalize ISBN

    Args:
        isbn: ISBN to normalize

    Returns:
        Dictionary with normalized ISBN data
    """
    api = ISBNdbAPI()
    return api.normalize_isbn(isbn)


if __name__ == "__main__":
    # Test the ISBNdb API
    test_isbn = "9780134685991"  # Effective Java

    print(f"Testing ISBNdb API with ISBN: {test_isbn}")
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
