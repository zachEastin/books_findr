"""
Book Price Tracker - ISBN Metadata Management
Handles storage and retrieval of book metadata (titles, authors, etc.)
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
ISBN_METADATA_CSV = DATA_DIR / "isbn_metadata.csv"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# CSV columns for ISBN metadata
ISBN_METADATA_COLUMNS = [
    "isbn_input",  # Original ISBN as entered by user
    "isbn13",  # Normalized ISBN-13
    "isbn10",  # Normalized ISBN-10
    "title",  # Book title
    "authors",  # Authors (comma-separated)
    "publisher",  # Publisher
    "year",  # Publication year
    "added_date",  # When added to our system
    "source",  # Where metadata came from (isbndb, manual, etc.)
    "notes",  # Additional notes
]


def initialize_isbn_metadata_csv():
    """Initialize the ISBN metadata CSV file if it doesn't exist"""
    if not ISBN_METADATA_CSV.exists():
        df = pd.DataFrame(columns=ISBN_METADATA_COLUMNS)
        df.to_csv(ISBN_METADATA_CSV, index=False)
        logger.info(f"Created ISBN metadata CSV: {ISBN_METADATA_CSV}")


def load_isbn_metadata() -> pd.DataFrame:
    """Load ISBN metadata from CSV file"""
    try:
        if ISBN_METADATA_CSV.exists():
            df = pd.read_csv(ISBN_METADATA_CSV)
            logger.debug(f"Loaded {len(df)} ISBN metadata records")
            return df
        else:
            initialize_isbn_metadata_csv()
            return pd.DataFrame(columns=ISBN_METADATA_COLUMNS)
    except Exception as e:
        logger.error(f"Error loading ISBN metadata: {e}")
        return pd.DataFrame(columns=ISBN_METADATA_COLUMNS)


def save_isbn_metadata(metadata: Dict) -> bool:
    """
    Save or update ISBN metadata

    Args:
        metadata: Dictionary with ISBN metadata

    Returns:
        True if successful, False otherwise
    """
    try:
        # Load existing data
        df = load_isbn_metadata()

        # Prepare the record
        record = {
            "isbn_input": metadata.get("isbn_input", ""),
            "isbn13": metadata.get("isbn13", ""),
            "isbn10": metadata.get("isbn10", ""),
            "title": metadata.get("title", ""),
            "authors": ", ".join(metadata.get("authors", []))
            if isinstance(metadata.get("authors"), list)
            else metadata.get("authors", ""),
            "publisher": metadata.get("publisher", ""),
            "year": metadata.get("year", ""),
            "added_date": datetime.now().isoformat(),
            "source": metadata.get("source", "unknown"),
            "notes": metadata.get("notes", ""),
        }

        # Check if ISBN already exists (by ISBN-13 or ISBN-10 or input)
        existing_mask = (
            (df["isbn13"] == record["isbn13"])
            | (df["isbn10"] == record["isbn10"])
            | (df["isbn_input"] == record["isbn_input"])
        )

        if existing_mask.any():
            # Update existing record
            for col, value in record.items():
                if col != "added_date":  # Don't update the original added date
                    df.loc[existing_mask, col] = value
            logger.info(f"Updated ISBN metadata for: {record['isbn_input']}")
        else:
            # Add new record
            new_df = pd.DataFrame([record])
            df = pd.concat([df, new_df], ignore_index=True)
            logger.info(f"Added new ISBN metadata for: {record['isbn_input']}")

        # Save to CSV
        df.to_csv(ISBN_METADATA_CSV, index=False)
        return True

    except Exception as e:
        logger.error(f"Error saving ISBN metadata: {e}")
        return False


def get_isbn_metadata(isbn: str) -> Optional[Dict]:
    """
    Get metadata for a specific ISBN

    Args:
        isbn: ISBN to look up (any format)

    Returns:
        Dictionary with metadata or None if not found
    """
    try:
        df = load_isbn_metadata()

        if df.empty:
            return None

        # Clean input ISBN
        clean_isbn = isbn.replace("-", "").replace(" ", "")

        # Search for matching record
        mask = (
            (df["isbn13"] == clean_isbn)
            | (df["isbn10"] == clean_isbn)
            | (df["isbn_input"] == isbn)
            | (df["isbn_input"] == clean_isbn)
        )

        matching_records = df[mask]

        if not matching_records.empty:
            # Return the first match as a dictionary
            record = matching_records.iloc[0].to_dict()

            # Convert authors back to list if it's a string
            if isinstance(record["authors"], str) and record["authors"]:
                record["authors"] = [author.strip() for author in record["authors"].split(",")]

            return record

        return None

    except Exception as e:
        logger.error(f"Error getting ISBN metadata for {isbn}: {e}")
        return None


def get_all_isbn_metadata() -> List[Dict]:
    """
    Get all ISBN metadata records

    Returns:
        List of dictionaries with ISBN metadata
    """
    try:
        df = load_isbn_metadata()

        records = []
        for _, row in df.iterrows():
            record = row.to_dict()

            # Convert authors back to list if it's a string
            if isinstance(record["authors"], str) and record["authors"]:
                record["authors"] = [author.strip() for author in record["authors"].split(",")]

            records.append(record)

        return records

    except Exception as e:
        logger.error(f"Error getting all ISBN metadata: {e}")
        return []


def delete_isbn_metadata(isbn: str) -> bool:
    """
    Delete metadata for a specific ISBN

    Args:
        isbn: ISBN to delete (any format)

    Returns:
        True if successful, False otherwise
    """
    try:
        df = load_isbn_metadata()

        if df.empty:
            return False

        # Clean input ISBN
        clean_isbn = isbn.replace("-", "").replace(" ", "")

        # Find matching records
        mask = (
            (df["isbn13"] == clean_isbn)
            | (df["isbn10"] == clean_isbn)
            | (df["isbn_input"] == isbn)
            | (df["isbn_input"] == clean_isbn)
        )

        if mask.any():
            # Remove matching records
            df = df[~mask]
            df.to_csv(ISBN_METADATA_CSV, index=False)
            logger.info(f"Deleted ISBN metadata for: {isbn}")
            return True

        return False

    except Exception as e:
        logger.error(f"Error deleting ISBN metadata for {isbn}: {e}")
        return False


def get_title_for_isbn(isbn: str) -> Optional[str]:
    """
    Get just the title for a specific ISBN (convenience function)

    Args:
        isbn: ISBN to look up

    Returns:
        Book title or None if not found
    """
    metadata = get_isbn_metadata(isbn)
    return metadata.get("title") if metadata else None


def get_isbn13_for_isbn(isbn: str) -> Optional[str]:
    """
    Get the ISBN-13 for a specific ISBN (convenience function)

    Args:
        isbn: ISBN to look up

    Returns:
        ISBN-13 or None if not found
    """
    metadata = get_isbn_metadata(isbn)
    return metadata.get("isbn13") if metadata else None


if __name__ == "__main__":
    # Test the ISBN metadata system
    print("Testing ISBN Metadata System")
    print("=" * 40)

    # Initialize the CSV
    initialize_isbn_metadata_csv()

    # Test data
    test_metadata = {
        "isbn_input": "9780134685991",
        "isbn13": "9780134685991",
        "isbn10": "0134685997",
        "title": "Effective Java",
        "authors": ["Joshua Bloch"],
        "publisher": "Addison-Wesley Professional",
        "year": "2017",
        "source": "test",
        "notes": "Test record",
    }

    # Save test metadata
    print("1. Saving test metadata...")
    success = save_isbn_metadata(test_metadata)
    print(f"   Success: {success}")

    # Retrieve metadata
    print("\n2. Retrieving metadata...")
    retrieved = get_isbn_metadata("9780134685991")
    print(f"   Retrieved: {retrieved}")

    # Get just the title
    print("\n3. Getting title...")
    title = get_title_for_isbn("9780134685991")
    print(f"   Title: {title}")

    # Get all metadata
    print("\n4. Getting all metadata...")
    all_metadata = get_all_isbn_metadata()
    print(f"   Total records: {len(all_metadata)}")

    print("\nTest completed!")
