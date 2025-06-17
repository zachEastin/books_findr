"""
Book Price Tracker - Flask Web Application
Main entry point for the web interface
"""

from flask import Flask, render_template, jsonify, request, make_response
import pandas as pd
from datetime import datetime
import logging
from pathlib import Path
import json
import html
import io
import asyncio
from threading import Lock
import traceback

# Import visualization module
try:
    from visualization import generate_dashboard_charts
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    logging.warning("Visualization module not available - charts will be disabled")

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "book-price-tracker-secret-key"

# Setup paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PRICES_CSV = DATA_DIR / "prices.csv"
LOGS_DIR = BASE_DIR / "logs"
GRADES_FILE = DATA_DIR / "grades.json"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOGS_DIR / "app.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

grade_db_lock = Lock()


def load_prices_data():
    """Load prices data from CSV file"""
    try:
        if PRICES_CSV.exists():
            # Load with ISBN as string to avoid integer conversion
            df = pd.read_csv(PRICES_CSV, dtype={'isbn': str}, keep_default_na=False, na_values=[""])
            logger.info(f"Loaded {len(df)} price records from CSV")
            return df
        else:
            logger.warning("prices.csv not found, creating empty DataFrame")
            # Create empty DataFrame with expected columns
            df = pd.DataFrame(columns=["timestamp", "isbn", "book_title", "title", "source", "price", "url", "notes"])
            return df
    except Exception as e:
        logger.error(f"Error loading prices data: {e}")
        return pd.DataFrame(columns=["timestamp", "isbn", "book_title", "title", "source", "price", "url", "notes"])


def create_sample_data():
    """Create sample data if CSV doesn't exist"""
    if not PRICES_CSV.exists():
        sample_data = [
            {
                "timestamp": datetime.now().isoformat(),
                "isbn": "9780134685991",
                "book_title": "Effective Java",
                "title": "Effective Java",
                "source": "Christianbook",
                "price": 42.50,
                "url": "https://christianbook.com/...",
                "notes": "Sample data",
            },
        ]
        df = pd.DataFrame(sample_data)
        df.to_csv(PRICES_CSV, index=False)
        logger.info("Created sample prices.csv file")


@app.route("/")
def index():
    """Main dashboard showing price data"""
    try:
        df = load_prices_data()

        # Get latest prices for each ISBN/source combination
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            latest_prices = df.sort_values("timestamp").groupby(["isbn", "source"]).tail(1)

            # Convert to dict for template
            prices_data = latest_prices.to_dict("records")

            # Generate charts if available
            charts = {}
            if CHARTS_AVAILABLE:
                try:
                    charts = generate_dashboard_charts(df)
                except Exception as e:
                    logger.error(f"Error generating charts: {e}")
        else:
            prices_data = []
            charts = {}

        books_file = BASE_DIR / "books.json"
        books = json.loads(books_file.read_bytes()) if books_file.exists() else {}

        return render_template(
            "index.html",
            prices=prices_data,
            books=books,
            total_records=len(df) if not df.empty else 0,
            charts=charts,
        )

    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return render_template(
            "index.html", prices=[], books={}, total_records=0, charts={}, error=str(e)
        )


@app.route("/api/prices")
def api_prices():
    """API endpoint to get prices data as JSON"""
    try:
        df = load_prices_data()
        return jsonify(df.to_dict("records"))
    except Exception as e:
        logger.error(f"Error in API prices endpoint: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/prices/<isbn>")
def api_prices_by_isbn(isbn):
    """API endpoint to get prices for a specific ISBN"""
    try:
        df = load_prices_data()
        isbn_data = df[df["isbn"] == isbn]
        return jsonify(isbn_data.to_dict("records"))
    except Exception as e:
        logger.error(f"Error getting prices for ISBN {isbn}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "csv_exists": PRICES_CSV.exists(),
            "total_records": len(load_prices_data()) if PRICES_CSV.exists() else 0,
        }
    )


@app.route("/admin")
def admin():
    """Admin interface for managing ISBNs"""
    return render_template("admin.html")


@app.route("/api/books")
def get_books():
    """Return all tracked books with their ISBN metadata"""
    try:
        books_file = BASE_DIR / "books.json"
        books = json.loads(books_file.read_bytes()) if books_file.exists() else {}
        return jsonify(books)
    except Exception as e:
        logger.error(f"Error loading books: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/books", methods=["POST"])
def add_book_isbn():
    """Add a new ISBN under a book title or update icon_url if patch_icon is set"""
    try:
        from scripts.google_books_api import GoogleBooksAPI
        data = request.json or {}
        title = data.get("title", "").strip()
        isbn_input = data.get("isbn", "").strip()
        author = data.get("author", "").strip()
        icon_url = data.get("icon_url", "").strip()
        patch_icon = data.get("patch_icon", False)
        grade = data.get("grade", "").strip()

        books_file = BASE_DIR / "books.json"
        books = json.loads(books_file.read_bytes()) if books_file.exists() else {}

        if patch_icon and title and isbn_input and icon_url:
            # Only update icon_url for the given ISBN
            isbn_list = books.get(title, [])
            updated = False
            for item in isbn_list:
                if isbn_input in item:
                    item[isbn_input]["icon_url"] = icon_url
                    updated = True
                    break
            if updated:
                books_file.write_text(json.dumps(books, indent=4))
                logger.info(f"Updated icon_url for {isbn_input} under {title}")
                return jsonify({"message": "Icon updated"})
            else:
                return jsonify({"error": "ISBN not found for icon update"}), 404

        books_file = BASE_DIR / "books.json"
        books = json.loads(books_file.read_bytes()) if books_file.exists() else {}

        # Ensure book entry exists
        # If title is not provided, try to get it from Google Books metadata after processing ISBN
        # We'll set the title variable after fetching metadata if needed
        original_title = title  # Save what user provided
        already_tracked = False
        isbn_list = books.setdefault(title, []) if title else None
        for t, lst in books.items():
            for item in lst:
                if isbn_input in item:
                    already_tracked = True
                    break
            if already_tracked:
                break
        if already_tracked:
            # Show which title the ISBN is tracked under
            tracked_title = title or original_title or isbn_input or 'this book'
            return jsonify({"error": f"ISBN is already tracked in '{tracked_title}'!"}), 400

        isbn_dict = {}
        
        # Helper function to process a single ISBN
        async def process_isbn(isbn):
            result = {"isbn": isbn, "success": False, "error": None, "metadata": None}
            clean_isbn = isbn.replace("-", "").replace(" ", "")
            if len(clean_isbn) not in [10, 13]:
                result["error"] = "Invalid ISBN format"
                return result
            if isbn in isbn_dict:
                result["error"] = "ISBN already being tracked"
                return result
            google_books_api = GoogleBooksAPI()
            metadata_result = {"success": False, "source": "manual"}
            if google_books_api.is_available():
                logger.info(f"Fetching metadata for ISBN {isbn} from Google Books...")
                metadata_result = google_books_api.fetch_book_metadata(isbn)
                metadata_result["source"] = "google_books"                        # Try to fetch Google Books thumbnail/icon
                if metadata_result.get("success") and "imageLinks" in metadata_result:
                    # Already present (future-proof)
                    pass
                elif metadata_result.get("success") and metadata_result.get("isbn13"):
                    # Try to fetch image from Google Books API directly
                    try:
                        # Use Google Books API to get volume info for this ISBN
                        import requests
                        gb_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{clean_isbn}"
                        resp = requests.get(gb_url, timeout=10)
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("totalItems", 0) > 0:
                                volume_info = data["items"][0]["volumeInfo"]
                                image_links = volume_info.get("imageLinks", {})
                                # Prefer thumbnail, fallback to smallThumbnail
                                icon_url = image_links.get("thumbnail") or image_links.get("smallThumbnail")
                                if icon_url:
                                    metadata_result["icon_url"] = icon_url
                                    
                                    # Download the icon and save locally
                                    try:
                                        from scripts.image_downloader import download_googlebooks_icon
                                        download_result = download_googlebooks_icon(isbn, icon_url)
                                        if download_result["success"]:
                                            # Add the local path to the metadata
                                            metadata_result["icon_path"] = download_result["image_path"]
                                            logger.info(f"Downloaded Google Books icon for ISBN {isbn}")
                                    except Exception as e:
                                        logger.warning(f"Failed to download Google Books icon for {isbn}: {e}")
                    except Exception as e:
                        logger.warning(f"Could not fetch Google Books icon for {isbn}: {e}")
            else:
                logger.warning("Google Books API not available, adding ISBN without metadata")
                metadata_result = google_books_api.normalize_isbn(isbn)
                metadata_result["source"] = "manual"
            if metadata_result.get("success") or metadata_result.get("isbn13"):
                metadata_result["isbn_input"] = isbn
                logger.info(f"Saved metadata for ISBN {isbn}")
                isbn_dict[isbn] = {
                    "title": metadata_result.get("title", ""),
                    "isbn13": metadata_result.get("isbn13", ""),
                    "isbn10": metadata_result.get("isbn10", ""),
                    "authors": metadata_result.get("authors", []),
                    "year": metadata_result.get("year", ""),
                    "source": metadata_result.get("source", "manual"),
                    "notes": metadata_result.get("notes", ""),
                    "icon_url": metadata_result.get("icon_url", ""),
                }
                result["success"] = True
                result["metadata"] = metadata_result
            else:
                result["error"] = metadata_result.get("error", "Unknown error")
            return result

        added = 0
        if isbn_input or (title and author):
            if isbn_input:
                result = asyncio.run(process_isbn(isbn_input))
                # If title was not provided, try to get it from metadata
                if not original_title:
                    title_from_metadata = result["metadata"].get("title") if result["metadata"] else None
                    if title_from_metadata:
                        title = title_from_metadata.strip()                    # Move the ISBN under the derived title in books.json
                        isbn_list = books.setdefault(title, [])
                    else:
                        title = isbn_input  # fallback to ISBN as title
                        isbn_list = books.setdefault(title, [])
                
                if result["success"]:
                    isbn_list.append({isbn_input: result["metadata"]})
                    added = 1
                else:
                    # Return structured response to trigger manual entry form
                    return jsonify({
                        "error": result["error"],
                        "show_manual_form": True,
                        "prefill_data": {
                            "title": title if title else "",
                            "isbn": isbn_input,
                            "authors": "",
                            "grade": grade if grade else ""
                        }
                    }), 400
            else:
                # Require author if adding by title only
                if not author:
                    return jsonify({"error": "Author is required when adding by title"}), 400
                google_books_api = GoogleBooksAPI()
                search_results = google_books_api.search_by_title_and_author(title, author=author, max_results=5)
                if not search_results:
                    # Return structured response to trigger manual entry form
                    return jsonify({
                        "error": "No ISBNs found for title and author",
                        "show_manual_form": True,
                        "prefill_data": {
                            "title": title if title else "",
                            "isbn": "",
                            "authors": author if author else "",
                            "grade": grade if grade else ""
                        }
                    }), 400
                seen = set()
                for item in search_results:
                    isbn_candidate = item.get("isbn13") or item.get("isbn10")
                    if not isbn_candidate or isbn_candidate in seen:
                        continue
                    if any(isbn_candidate in x for x in isbn_list):
                        continue
                    result = asyncio.run(process_isbn(isbn_candidate))
                    if result["success"]:
                        isbn_list.append({isbn_candidate: result["metadata"]})
                        added += 1
                    seen.add(isbn_candidate)
        if added:
            books_file.write_text(json.dumps(books, indent=4))
            logger.info(f"Added {added} ISBNs under {title}")
            # Assign to grade level if specified
            if grade:
                try:
                    with grade_db_lock:
                        grades = load_grades()
                        if grade not in grades:
                            grades[grade] = []
                        if title not in grades[grade]:
                            grades[grade].append(title)
                            save_grades(grades)
                            logger.info(f"Assigned '{title}' to {grade}")
                except Exception as e:
                    logger.error(f"Error assigning book to grade: {e}")
                    # Don't fail the entire operation if grade assignment fails
            # Custom message: single or multiple ISBNs
            if added == 1:
                return jsonify({"message": f"Added '{title}'!"})
            else:
                return jsonify({"message": f"Added '{title}' and {added-1} Related ISBNs!"})
        else:
            return jsonify({"error": "No ISBNs added"}), 400

    except Exception as e:
        logger.error(f"Error adding ISBN: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/books/<title>/<isbn>", methods=["DELETE"])
def remove_isbn(title, isbn):
    """Remove a specific ISBN from a book"""
    try:
        books_file = BASE_DIR / "books.json"

        if not books_file.exists():
            return jsonify({"error": "No books file found"}), 404

        books = json.loads(books_file.read_bytes())

        if title not in books:
            return jsonify({"error": "Book title not found"}), 404

        isbn_list = books[title]
        new_list = [item for item in isbn_list if isbn not in item]
        if len(new_list) == len(isbn_list):
            return jsonify({"error": "ISBN not found"}), 404

        books[title] = new_list
        books_file.write_text(json.dumps(books, indent=4))

        return jsonify({"message": f"ISBN {isbn} removed from {title}"})

    except Exception as e:
        logger.error(f"Error removing ISBN: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/books/search", methods=["POST"])
def search_books():
    """Search for books by title, author, or ISBN"""
    try:
        data = request.json or {}
        query = data.get("query", "").strip()
        search_type = data.get("type", "auto")  # auto, title, author, isbn
        
        if not query:
            return jsonify({"error": "Search query is required"}), 400
        
        results = []
        
        # Import Google Books API
        try:
            from scripts.google_books_api import GoogleBooksAPI
            google_books_api = GoogleBooksAPI()
        except ImportError:
            return jsonify({"error": "Google Books API not available"}), 500
        
        if search_type == "isbn" or (search_type == "auto" and query.replace("-", "").replace(" ", "").isdigit()):
            # Search by ISBN
            clean_isbn = query.replace("-", "").replace(" ", "")
            if len(clean_isbn) in [10, 13]:
                metadata = google_books_api.fetch_book_metadata(clean_isbn)
                if metadata.get("success") and metadata.get("title"):
                    results.append({
                        "title": metadata["title"],
                        "authors": metadata.get("authors", []),
                        "publisher": metadata.get("publisher", ""),
                        "year": metadata.get("year", ""),
                        "isbn13": metadata.get("isbn13", ""),
                        "isbn10": metadata.get("isbn10", ""),
                        "icon_url": metadata.get("icon_url", ""),
                        "search_type": "isbn"
                    })
        
        if not results and search_type in ["title", "author", "auto"]:
            # Search by title (and possibly author)
            search_terms = query.split(" by ")
            if len(search_terms) == 2:
                # Format: "Book Title by Author Name"
                title_part = search_terms[0].strip()
                author_part = search_terms[1].strip()
            else:
                title_part = query
                author_part = None
            
            search_results = google_books_api.search_by_title_and_author(title_part, author_part, max_results=10)
            
            for book in search_results:
                if book.get("title"):
                    results.append({
                        "title": book["title"],
                        "authors": book.get("authors", []),
                        "publisher": book.get("publisher", ""),
                        "year": book.get("year", ""),
                        "isbn13": book.get("isbn13", ""),
                        "isbn10": book.get("isbn10", ""),
                        "icon_url": book.get("icon_url", ""),
                        "search_type": "title"
                    })
        
        return jsonify({
            "query": query,
            "results": results,
            "total_results": len(results),
            "search_successful": len(results) > 0
        })
    
    except Exception as e:
        logger.error(f"Error searching books: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/scrape/<isbn>", methods=["POST"])
def trigger_scrape(isbn):
    """Trigger scraping for a specific ISBN"""
    try:
        from scripts.scraper import scrape_all_sources, save_results_to_csv

        # Load books file and locate metadata
        books = json.loads((BASE_DIR / "books.json").read_bytes())

        isbn_item = None
        book_title = None
        for title, items in books.items():
            for entry in items:
                if isbn in entry:
                    isbn_item = entry[isbn]
                    book_title = title
                    break
            if isbn_item:
                break

        if not isbn_item:
            return jsonify({"error": "ISBN not found"}), 404

        logger.info(
            f"Manual scrape triggered for '{book_title}' ISBN: {isbn}"
        )
        results = scrape_all_sources(isbn_item, book_title)

        if results:
            save_results_to_csv(results)
            return jsonify(
                {"message": f"Scraping completed for {isbn}", "results_count": len(results), "results": results}
            )
        else:
            return jsonify({"message": f"No results found for {isbn}", "results_count": 0})

    except Exception as e:
        logger.error(f"Error during manual scrape: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/scrape/all", methods=["POST"])
async def trigger_bulk_scrape():
    """Trigger bulk scraping for all tracked ISBNs"""
    try:
        from scripts.scraper import scrape_all_isbns, load_isbns_from_file

        # Get list of book/isbn tuples first
        isbns = load_isbns_from_file()

        if not isbns:
            return jsonify({"error": "No ISBNs found to scrape"}), 400

        logger.info(f"Bulk scrape triggered for {len(isbns)} ISBNs")

        # Start the bulk scraping process
        await scrape_all_isbns()

        return jsonify({"message": f"Bulk scraping completed for {len(isbns)} ISBNs", "isbn_count": len(isbns)})

    except Exception as e:
        logger.error(f"Error during bulk scrape: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/prices/recent")
def get_recent_prices():
    """Get recent price records for activity log"""
    try:
        df = load_prices_data()
        if df.empty:
            return jsonify([])

        # Sort by timestamp and get latest 20 records
        df_recent = df.sort_values("timestamp", ascending=False).head(20)

        # Convert to list of dictionaries and replace np.nan with None
        records = df_recent.to_dict("records")
        # Replace np.nan with None recursively
        import numpy as np
        def clean_nans(obj):
            if isinstance(obj, dict):
                return {k: clean_nans(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_nans(v) for v in obj]
            elif isinstance(obj, float) and np.isnan(obj):
                return None
            else:
                return obj
        records = clean_nans(records)
        
        return jsonify(records)

    except Exception as e:
        logger.error(f"Error loading recent prices: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/export/csv")
def export_csv():
    """Export prices data as CSV file"""
    try:
        df = load_prices_data()

        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)

        response = make_response(output.getvalue())
        response.headers["Content-Type"] = "text/csv"
        response.headers["Content-Disposition"] = (
            f"attachment; filename=book_prices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        return response
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        return jsonify({"error": str(e)}), 500


def generate_html_price_report(data):
    """Generate a self-contained HTML report from price data"""
    
    # Get current timestamp for report generation
    report_timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    
    # Start building HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Book Price Report - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f8f9fa;
            padding: 20px;
        }}
        
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
        }}
        
        .header p {{
            opacity: 0.9;
            font-size: 1.1em;
        }}
        
        .content {{
            padding: 20px;
        }}
        
        .book-section {{
            margin-bottom: 40px;
            border-bottom: 2px solid #eee;
            padding-bottom: 30px;
        }}
        
        .book-section:last-child {{
            border-bottom: none;
            margin-bottom: 0;
        }}
        
        .book-title {{
            font-size: 1.8em;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
            padding-left: 15px;
        }}
        
        .book-meta {{
            color: #7f8c8d;
            margin-bottom: 20px;
            font-size: 0.9em;
        }}
        
        .best-price {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }}
        
        .best-price h3 {{
            margin-bottom: 10px;
            font-size: 1.2em;
        }}
        
        .best-price .price {{
            font-size: 2.2em;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .best-price .source {{
            opacity: 0.9;
            margin-bottom: 15px;
        }}
        
        .best-price a {{
            display: inline-block;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            padding: 12px 24px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: 500;
            transition: all 0.3s ease;
            border: 2px solid rgba(255, 255, 255, 0.3);
        }}
        
        .best-price a:hover {{
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }}
        
        .all-prices {{
            margin-top: 20px;
        }}
        
        .all-prices h4 {{
            color: #34495e;
            margin-bottom: 15px;
            font-size: 1.1em;
        }}
        
        .price-grid {{
            display: grid;
            gap: 12px;
        }}
        
        .price-item {{
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            padding: 15px;
            transition: all 0.3s ease;
        }}
        
        .price-item:hover {{
            background: #e9ecef;
            border-color: #667eea;
            transform: translateY(-1px);
        }}
        
        .price-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        
        .source-name {{
            font-weight: 600;
            color: #2c3e50;
        }}
        
        .price-value {{
            font-size: 1.3em;
            font-weight: bold;
            color: #27ae60;
        }}
        
        .price-link {{
            display: inline-block;
            color: #667eea;
            text-decoration: none;
            font-size: 0.9em;
            margin-top: 5px;
            padding: 6px 12px;
            background: rgba(102, 126, 234, 0.1);
            border-radius: 4px;
            transition: all 0.3s ease;
        }}
        
        .price-link:hover {{
            background: rgba(102, 126, 234, 0.2);
            color: #5a6cb8;
        }}
        
        .no-price {{
            color: #e74c3c;
            font-style: italic;
        }}
        
        .summary {{
            background: #e8f4fd;
            border-left: 4px solid #3498db;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 0 6px 6px 0;
        }}
        
        .summary h3 {{
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        
        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        
        .stat-item {{
            text-align: center;
            padding: 10px;
            background: white;
            border-radius: 6px;
        }}
        
        .stat-value {{
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .stat-label {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        
        .footer {{
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        
        @media (max-width: 600px) {{
            body {{
                padding: 10px;
            }}
            
            .header h1 {{
                font-size: 2em;
            }}
            
            .book-title {{
                font-size: 1.5em;
            }}
            
            .best-price .price {{
                font-size: 1.8em;
            }}
            
            .summary-stats {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📚 Book Price Report</h1>
            <p>Generated on {report_timestamp}</p>
        </div>
        
        <div class="content">"""
    
    # Add summary statistics
    total_books = len(data)
    total_sources = set()
    all_prices = []
    
    for isbn_data in data.values():
        for price_record in isbn_data['prices']:
            if price_record.get('success') == 'True' and price_record.get('price'):
                total_sources.add(price_record['source'])
                all_prices.append(price_record['price'])
    
    avg_price = sum(all_prices) / len(all_prices) if all_prices else 0
    min_price = min(all_prices) if all_prices else 0
    max_price = max(all_prices) if all_prices else 0
    
    html_content += f"""
            <div class="summary">
                <h3>📊 Report Summary</h3>
                <p>Latest pricing information for all tracked books</p>
                <div class="summary-stats">
                    <div class="stat-item">
                        <div class="stat-value">{total_books}</div>
                        <div class="stat-label">Books Tracked</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{len(total_sources)}</div>
                        <div class="stat-label">Price Sources</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${avg_price:.2f}</div>
                        <div class="stat-label">Average Price</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${min_price:.2f} - ${max_price:.2f}</div>
                        <div class="stat-label">Price Range</div>
                    </div>
                </div>
            </div>"""
    
    # Process each book
    for isbn, book_data in data.items():
        title = html.escape(book_data['title'])
        
        # Get latest prices from each source (successful ones only)
        latest_prices = []
        for price_record in book_data['prices']:
            if price_record.get('success') == 'True' and price_record.get('price') is not None:
                latest_prices.append(price_record)
        
        # Sort by timestamp to get the most recent from each source
        price_by_source = {}
        for price in latest_prices:
            source = price['source']
            timestamp = price['timestamp']
            if source not in price_by_source or timestamp > price_by_source[source]['timestamp']:
                price_by_source[source] = price
        
        current_prices = list(price_by_source.values())
        
        # Find best price
        best_price = None
        if current_prices:
            best_price = min(current_prices, key=lambda x: x['price'])
        
        html_content += f"""
            <div class="book-section">
                <h2 class="book-title">{title}</h2>
                <div class="book-meta">
                    ISBN: {html.escape(isbn)} • Last Updated: {book_data.get('latest_update', 'Unknown')}
                </div>"""
        
        if best_price:
            best_url = html.escape(best_price['url']) if best_price.get('url') else '#'
            best_source = html.escape(best_price['source'])
            
            html_content += f"""
                <div class="best-price">
                    <h3>🏆 Best Price Found</h3>
                    <div class="price">${best_price['price']:.2f}</div>
                    <div class="source">from {best_source}</div>
                    <a href="{best_url}" target="_blank">🛒 View Deal</a>
                </div>"""
        
        if current_prices:
            html_content += """
                <div class="all-prices">
                    <h4>💰 All Current Prices</h4>
                    <div class="price-grid">"""
            
            # Sort prices by value
            sorted_prices = sorted(current_prices, key=lambda x: x['price'])
            
            for price in sorted_prices:
                source = html.escape(price['source'])
                price_val = price['price']
                url = html.escape(price.get('url', '')) if price.get('url') else '#'
                
                # Highlight if this is the best price
                extra_class = ' style="border-color: #667eea; border-width: 2px;"' if price == best_price else ''
                
                html_content += f"""
                        <div class="price-item"{extra_class}>
                            <div class="price-header">
                                <span class="source-name">{source}</span>
                                <span class="price-value">${price_val:.2f}</span>
                            </div>
                            <a href="{url}" target="_blank" class="price-link">🔗 View on {source}</a>
                        </div>"""
            
            html_content += """
                    </div>
                </div>"""
        else:
            html_content += """
                <div class="all-prices">
                    <p class="no-price">⚠️ No current pricing data available</p>
                </div>"""
        
        html_content += """
            </div>"""
    
    # Close HTML
    html_content += """
        </div>
        
        <div class="footer">
            <p>📱 This report works on all devices • Generated by BooksFindr Price Tracker</p>
            <p>Tap any "View Deal" or "View on [Source]" link to open the book's page</p>
        </div>
    </div>
</body>
</html>"""
    
    return html_content


@app.route("/export/html")
def export_html():
    """Export prices data as a self-contained HTML report"""
    try:
        df = load_prices_data()
        
        if df.empty:
            return jsonify({"error": "No data available for report"}), 400
        
        # Process data for the report
        result = {}
        
        for isbn in df["isbn"].unique():
            isbn_data = df[df["isbn"] == isbn]
            
            # Get book title - prioritize ISBNdb metadata over price data
            title = "Unknown Title"
            try:
                isbn_metadata = json.loads((BASE_DIR / "books.json").read_bytes())
                metadata = isbn_metadata.get(str(isbn))
                if metadata and metadata.get("title"):
                    title = str(metadata["title"])
                else:
                    price_title_data = isbn_data[isbn_data["title"].notna() & (isbn_data["title"] != "")]
                    if len(price_title_data) > 0:
                        title = str(price_title_data["title"].iloc[0])
            except Exception as e:
                logger.warning(f"Error getting title for {isbn}: {e}")
                price_title_data = isbn_data[isbn_data["title"].notna() & (isbn_data["title"] != "")]
                if len(price_title_data) > 0:
                    title = str(price_title_data["title"].iloc[0])
            
            isbn_stats = {
                "isbn": str(isbn),
                "title": str(title),
                "latest_update": str(isbn_data["timestamp"].max()) if not isbn_data["timestamp"].isna().all() else None,
                "prices": [],
            }
              # Add individual price records
            for _, row in isbn_data.iterrows():
                price_record = {
                    "source": str(row["source"]) if pd.notna(row["source"]) else "",
                    "price": float(row["price"]) if row["price"] and str(row["price"]).replace(".", "").isdigit() else None,
                    "url": str(row["url"]) if pd.notna(row["url"]) else "",
                    "timestamp": str(row["timestamp"]) if pd.notna(row["timestamp"]) else "",
                    "success": "True" if row["success"] else "False",
                }
                isbn_stats["prices"].append(price_record)
            
            result[str(isbn)] = isbn_stats
        
        # Generate HTML report
        html_content = generate_html_price_report(result)
        
        # Create response
        response = make_response(html_content)
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        response.headers["Content-Disposition"] = (
            f"attachment; filename=book_price_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating HTML report: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/summary")
def api_summary():
    """API endpoint to get summary statistics"""
    try:
        df = load_prices_data()

        if df.empty:
            return jsonify({"message": "No data available"})

        # Calculate statistics
        price_data = df[df["price"].notna() & (df["price"] != "")]

        if not price_data.empty:
            price_data["price"] = pd.to_numeric(price_data["price"], errors="coerce")
            price_data = price_data[price_data["price"].notna()]

            summary = {
                "total_records": len(df),
                "unique_books": df["isbn"].nunique(),
                "unique_sources": df["source"].nunique(),
                "price_stats": {
                    "min": float(price_data["price"].min()) if not price_data.empty else 0,
                    "max": float(price_data["price"].max()) if not price_data.empty else 0,
                    "mean": float(price_data["price"].mean()) if not price_data.empty else 0,
                    "median": float(price_data["price"].median()) if not price_data.empty else 0,
                },
                "success_rate": len(df[df["success"] == "True"]) / len(df) * 100 if len(df) > 0 else 0,
                "last_updated": df["timestamp"].max() if "timestamp" in df.columns else None,
            }
        else:
            summary = {
                "total_records": len(df),
                "unique_books": df["isbn"].nunique(),
                "unique_sources": df["source"].nunique(),
                "price_stats": {"min": 0, "max": 0, "mean": 0, "median": 0},
                "success_rate": 0,
                "last_updated": None,
            }

        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/prices-by-isbn")
def api_prices_by_isbn_grouped():
    """API endpoint to get prices grouped by ISBN with statistics"""
    try:

        df = load_prices_data()

        if df.empty:
            return jsonify({"message": "No data available", "data": {}})        # Group by ISBN and calculate statistics
        result = {}

        for isbn in df["isbn"].unique():
            isbn_data = df[df["isbn"] == isbn]

            # Get the most recent record for each source to calculate current min/max/avg prices
            isbn_data_sorted = isbn_data.sort_values("timestamp", ascending=False)
            latest_by_source = isbn_data_sorted.groupby("source").first().reset_index()            # Get valid prices from most recent records only (non-null, non-empty, successful)
            valid_latest_prices = latest_by_source[
                (latest_by_source["price"].notna()) & 
                (latest_by_source["price"] != "") &
                (latest_by_source["success"])
            ]
            
            if not valid_latest_prices.empty:
                valid_prices_numeric = pd.to_numeric(valid_latest_prices["price"], errors="coerce")
                valid_prices_numeric = valid_prices_numeric[valid_prices_numeric.notna()]
            else:
                valid_prices_numeric = pd.Series([])# Get book title - prioritize ISBNdb metadata over price data
            title = "Unknown Title"
            try:
                # First try to get title from ISBNdb metadata
                isbn_metadata = json.loads((BASE_DIR / "books.json").read_bytes())
                metadata = isbn_metadata.get(str(isbn))
                if metadata and metadata.get("title"):
                    title = str(metadata["title"])
                    logger.info(f"Using ISBNdb title for {isbn}: {title}")
                else:
                    # Fallback to title from price data
                    price_title_data = isbn_data[isbn_data["title"].notna() & (isbn_data["title"] != "")]
                    if len(price_title_data) > 0:
                        title = str(price_title_data["title"].iloc[0])
                        logger.info(f"Using price data title for {isbn}: {title}")
                    else:
                        logger.warning(f"No title found for {isbn}")
            except Exception as e:
                logger.warning(f"Error getting title for {isbn}: {e}")
                # Fallback to title from price data
                price_title_data = isbn_data[isbn_data["title"].notna() & (isbn_data["title"] != "")]
                if len(price_title_data) > 0:
                    title = str(price_title_data["title"].iloc[0])  # Calculate statistics
            isbn_stats = {
                "isbn": str(isbn),
                "title": str(title),
                "total_records": int(len(isbn_data)),
                "successful_records": int(len(isbn_data[isbn_data["success"] == "True"])),
                "sources": [str(source) for source in isbn_data["source"].unique().tolist()],
                "latest_update": str(isbn_data["timestamp"].max()) if not isbn_data["timestamp"].isna().all() else None,
                "prices": [],
            }

            if not valid_prices_numeric.empty:
                isbn_stats.update(
                    {
                        "min_price": float(valid_prices_numeric.min()),
                        "max_price": float(valid_prices_numeric.max()),
                        "avg_price": float(valid_prices_numeric.mean()),
                        "price_count": int(len(valid_prices_numeric)),
                    }
                )
            else:
                isbn_stats.update({"min_price": None, "max_price": None, "avg_price": None, "price_count": 0})

            # Add individual price records
            for _, row in isbn_data.iterrows():
                price_record = {
                    "source": str(row["source"]) if pd.notna(row["source"]) else "",
                    "price": float(row["price"])
                    if row["price"] and str(row["price"]).replace(".", "").isdigit()
                    else None,
                    "url": str(row["url"]) if pd.notna(row["url"]) else "",
                    "timestamp": str(row["timestamp"]) if pd.notna(row["timestamp"]) else "",
                    "success": str(row["success"]) if pd.notna(row["success"]) else "False",
                    "notes": str(row["notes"]) if pd.notna(row["notes"]) else "",
                }
                isbn_stats["prices"].append(price_record)

            result[str(isbn)] = isbn_stats

        return jsonify({"data": result, "total_isbns": len(result)})

    except Exception as e:
        logger.error(f"Error generating grouped ISBN data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/prices-by-book")
def api_prices_by_book_grouped():
    """API endpoint to get prices grouped by book title with ISBN breakdown"""
    try:
        df = load_prices_data()
        
        if df.empty:
            return jsonify({"message": "No data available", "data": {}})
        
        # Load books configuration to map ISBNs to book titles
        books_file = BASE_DIR / "books.json"
        if not books_file.exists():
            return jsonify({"error": "Books configuration not found"}, 500)
        
        books_config = json.loads(books_file.read_bytes())
        
        # Create ISBN to book title mapping
        isbn_to_book = {}
        for book_title, isbn_list in books_config.items():
            for isbn_item in isbn_list:
                for isbn_key, metadata in isbn_item.items():
                    # Map both the key ISBN and the ISBN13/ISBN10 from metadata
                    isbn_to_book[isbn_key] = book_title
                    if metadata.get('isbn13'):
                        isbn_to_book[metadata['isbn13']] = book_title
                    if metadata.get('isbn10'):
                        isbn_to_book[metadata['isbn10']] = book_title
        
        result = {}
        
        # Group by book title
        for book_title, isbn_list in books_config.items():
            # Get all ISBNs for this book
            book_isbns = []
            for isbn_item in isbn_list:
                for isbn_key, metadata in isbn_item.items():
                    book_isbns.extend([isbn_key, metadata.get('isbn13'), metadata.get('isbn10')])
            
            # Remove None values and duplicates
            book_isbns = list(set([isbn for isbn in book_isbns if isbn]))
            
            # Get data for all ISBNs belonging to this book
            book_data = df[df["isbn"].isin(book_isbns)]
            
            if book_data.empty:
                continue
            
            # Get the most recent record for each source across all ISBNs
            book_data_sorted = book_data.sort_values("timestamp", ascending=False)
            latest_by_source_isbn = book_data_sorted.groupby(["source", "isbn"]).first().reset_index()
            
            # Get valid prices from most recent records
            valid_latest_prices = latest_by_source_isbn[
                (latest_by_source_isbn["price"].notna()) & 
                (latest_by_source_isbn["price"] != "") &
                (latest_by_source_isbn["success"])
            ]
            
            if not valid_latest_prices.empty:
                valid_prices_numeric = pd.to_numeric(valid_latest_prices["price"], errors="coerce")
                valid_prices_numeric = valid_prices_numeric[valid_prices_numeric.notna()]
            else:
                valid_prices_numeric = pd.Series([])
            
            # Calculate overall book statistics
            all_prices_data = book_data[
                (book_data["price"].notna()) & 
                (book_data["price"] != "") &
                (book_data["success"])
            ]
            
            if not all_prices_data.empty:
                all_prices_numeric = pd.to_numeric(all_prices_data["price"], errors="coerce")
                all_prices_numeric = all_prices_numeric[all_prices_numeric.notna()]
            else:
                all_prices_numeric = pd.Series([])
            
            # Find historical lowest and highest prices
            lowest_price = None
            lowest_price_date = None
            highest_price = None
            highest_price_date = None
            
            if not all_prices_numeric.empty:
                lowest_idx = all_prices_data.loc[all_prices_numeric.idxmin()]
                highest_idx = all_prices_data.loc[all_prices_numeric.idxmax()]
                
                lowest_price = float(all_prices_numeric.min())
                lowest_price_date = str(lowest_idx["timestamp"])
                highest_price = float(all_prices_numeric.max())
                highest_price_date = str(highest_idx["timestamp"])
            
            # Get book icon URL from the first ISBN that has one
            icon_url = None
            for isbn_item in isbn_list:
                for isbn_key, metadata in isbn_item.items():
                    if metadata.get('icon_url'):
                        icon_url = metadata['icon_url']
                        break
                if icon_url:
                    break
            
            # Calculate book-level statistics
            book_stats = {
                "title": book_title,
                "isbns": book_isbns,
                "total_records": int(len(book_data)),
                "successful_records": int(len(book_data[book_data["success"]])),
                "sources": [str(source) for source in book_data["source"].unique().tolist()],
                "latest_update": str(book_data["timestamp"].max()) if not book_data["timestamp"].isna().all() else None,
                "icon_url": icon_url,
                "isbn_details": {},
                "lowest_price_ever": lowest_price,
                "lowest_price_date": lowest_price_date,
                "highest_price_ever": highest_price,
                "highest_price_date": highest_price_date,
            }
            
            # Current best price from most recent scrapes
            if not valid_prices_numeric.empty:
                book_stats.update({
                    "best_current_price": float(valid_prices_numeric.min()),
                    "worst_current_price": float(valid_prices_numeric.max()),
                    "avg_current_price": float(valid_prices_numeric.mean()),
                    "current_price_count": int(len(valid_prices_numeric)),
                })
                
                # Find the URL for the best current price
                best_price_record = valid_latest_prices[
                    pd.to_numeric(valid_latest_prices["price"], errors="coerce") == valid_prices_numeric.min()
                ].iloc[0]
                book_stats["best_price_url"] = str(best_price_record["url"]) if pd.notna(best_price_record["url"]) else ""
            else:
                book_stats.update({
                    "best_current_price": None,
                    "worst_current_price": None,
                    "avg_current_price": None,
                    "current_price_count": 0,
                    "best_price_url": ""
                })
            
            # Add individual ISBN details
            for isbn in book_isbns:
                isbn_data = book_data[book_data["isbn"] == isbn]
                if isbn_data.empty:
                    continue
                  # Get most recent prices for this ISBN
                isbn_sorted = isbn_data.sort_values("timestamp", ascending=False)
                isbn_latest_by_source = isbn_sorted.groupby("source").first().reset_index()
                
                isbn_valid_prices = isbn_latest_by_source[
                    (isbn_latest_by_source["price"].notna()) & 
                    (isbn_latest_by_source["price"] != "") &
                    (isbn_latest_by_source["success"])
                ]
                
                if not isbn_valid_prices.empty:
                    isbn_prices_numeric = pd.to_numeric(isbn_valid_prices["price"], errors="coerce")
                    isbn_prices_numeric = isbn_prices_numeric[isbn_prices_numeric.notna()]
                else:
                    isbn_prices_numeric = pd.Series([])
                  # Calculate ISBN statistics
                isbn_stats = {
                    "isbn": str(isbn),
                    "total_records": int(len(isbn_data)),
                    "successful_records": int(len(isbn_data[isbn_data["success"]])),
                    "sources": [str(source) for source in isbn_data["source"].unique().tolist()],
                    "latest_update": str(isbn_data["timestamp"].max()) if not isbn_data["timestamp"].isna().all() else None,
                    "prices": [],
                }
                
                if not isbn_prices_numeric.empty:
                    isbn_stats.update({
                        "min_price": float(isbn_prices_numeric.min()),
                        "max_price": float(isbn_prices_numeric.max()),
                        "avg_price": float(isbn_prices_numeric.mean()),
                        "price_count": int(len(isbn_prices_numeric)),
                    })
                else:
                    isbn_stats.update({
                        "min_price": None,
                        "max_price": None,
                        "avg_price": None,
                        "price_count": 0
                    })
                  # Add price records for this ISBN
                for _, row in isbn_data.iterrows():
                    price_record = {
                        "source": str(row["source"]) if pd.notna(row["source"]) else "",
                        "price": float(row["price"])
                        if row["price"] and str(row["price"]).replace(".", "").isdigit()
                        else None,
                        "url": str(row["url"]) if pd.notna(row["url"]) else "",
                        "timestamp": str(row["timestamp"]) if pd.notna(row["timestamp"]) else "",
                        "success": bool(row["success"]) if pd.notna(row["success"]) else False,
                        "notes": str(row["notes"]) if pd.notna(row["notes"]) else "",
                    }
                    isbn_stats["prices"].append(price_record)
                
                book_stats["isbn_details"][str(isbn)] = isbn_stats
            
            result[book_title] = book_stats
        
        return jsonify({"data": result, "total_books": len(result)})
    
    except Exception as e:
        logger.error(f"Error generating grouped book data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboard-data")
def api_dashboard_data():
    """API endpoint that returns merged book, grade, and price data for dashboard optimization"""
    try:
        # Load all required data
        books_data = load_books()  # { title: [ {isbn: {...meta}}, ... ] }
        grades_data = load_grades()  # { grade: [title, ...] }
        
        # Load prices data using existing endpoint logic
        df = load_prices_data()
        if df.empty:
            prices_data = {}
        else:
            import numpy as np
            def clean_nans(obj):
                if isinstance(obj, dict):
                    return {k: clean_nans(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_nans(v) for v in obj]
                elif isinstance(obj, float) and np.isnan(obj):
                    return None
                else:
                    return obj
            # prices_data = clean_nans(df.to_dict(orient='records'))

            # Group by book title and calculate statistics
            prices_data = {}
            for title, group in df.groupby('book_title'):
                if not isinstance(title, str) and np.isnan(title):
                    title = ""
                group = clean_nans(group)
                # Get successful records only
                successful_records = group[group['price'].notna() & (group['price'] > 0)]
                
                # Calculate basic stats
                stats = {
                    'title': title,
                    'total_records': len(group),
                    'successful_records': len(successful_records),
                    'current_price_count': 0,
                    'avg_current_price': None,
                    'best_current_price': None,
                    'best_price_url': None,
                    'sources': [],
                    'isbns': group['isbn'].unique().tolist(),
                    'isbn_details': {}
                }
                
                if not successful_records.empty:
                    # Get latest price from each source
                    latest_by_source = successful_records.loc[successful_records.groupby('source')['timestamp'].idxmax()]
                    current_prices = latest_by_source['price'].tolist()
                    
                    if current_prices:
                        stats['current_price_count'] = len(current_prices)
                        stats['avg_current_price'] = sum(current_prices) / len(current_prices)
                        stats['best_current_price'] = min(current_prices)
                        
                        # Find best price URL
                        best_price_row = latest_by_source[latest_by_source['price'] == stats['best_current_price']].iloc[0]
                        stats['best_price_url'] = best_price_row.get('url', '')
                        
                        # Get sources
                        stats['sources'] = latest_by_source['source'].tolist()
                    
                    # Calculate historical stats
                    all_prices = successful_records['price'].tolist()
                    stats['lowest_price_ever'] = min(all_prices)
                    stats['highest_price_ever'] = max(all_prices)
                    
                    # Get dates for min/max prices
                    min_price_row = successful_records[successful_records['price'] == stats['lowest_price_ever']].iloc[0]
                    max_price_row = successful_records[successful_records['price'] == stats['highest_price_ever']].iloc[0]
                    stats['lowest_price_date'] = min_price_row['timestamp']
                    stats['highest_price_date'] = max_price_row['timestamp']
                
                # Build ISBN details
                for isbn in stats['isbns']:
                    isbn_records = group[group['isbn'] == isbn]
                    isbn_successful = isbn_records[isbn_records['price'].notna() & (isbn_records['price'] > 0)]
                    
                    if not isinstance(isbn, str) and np.isnan(isbn):
                        isbn = ""
                    isbn_stats = {
                        'isbn': isbn,
                        'total_records': len(isbn_records),
                        'successful_records': len(isbn_successful),
                        'sources': [],
                        'prices': []
                    }
                    
                    if not isbn_successful.empty:
                        isbn_stats['sources'] = isbn_successful['source'].unique().tolist()
                        isbn_stats['avg_price'] = isbn_successful['price'].mean()
                        isbn_stats['min_price'] = isbn_successful['price'].min()
                        isbn_stats['max_price'] = isbn_successful['price'].max()
                        isbn_stats['price_count'] = len(isbn_successful)
                        
                        # Get recent prices for this ISBN
                        recent_prices = clean_nans(isbn_successful.tail(10).to_dict('records'))
                        isbn_stats['prices'] = recent_prices
                    
                    stats['isbn_details'][isbn] = isbn_stats
                
                prices_data[title] = stats
          # Create reverse mapping from book title to grade
        book_to_grade = {}
        for grade_name, book_list in grades_data.items():
            for book_title in book_list:
                book_to_grade[book_title] = grade_name
        
        logger.info(f"Created book_to_grade mapping with {len(book_to_grade)} entries")
        
        # Debug: Check specific grades
        debug_grades = ['Kindergarten', '4th Grade', '5th Grade', '6th Grade']
        for grade in debug_grades:
            books_in_grade = [title for title, g in book_to_grade.items() if g == grade]
            logger.info(f"{grade}: {len(books_in_grade)} books mapped")
        
        # Merge all data and organize by grade
        # Initialize with all grades from grades_data plus Unassigned
        books_by_grade = {'Unassigned': []}
        for grade_name in grades_data.keys():
            books_by_grade[grade_name] = []
        
        merged_data = {
            'books_by_grade': books_by_grade,
            'total_books': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        # Get all unique book titles
        all_titles = set(books_data.keys()) | set(prices_data.keys())
        
        for title in all_titles:
            # Get book metadata
            book_meta = books_data.get(title, [])
            # Get price data
            book_price_data = prices_data.get(title, {})
            
            # Create merged book object
            merged_book = {
                'title': title,
                'assigned_grade': book_to_grade.get(title, 'Unassigned'),
                'isbns': [],
                'authors': [],
                'icon_url': '',
                'icon_path': '',
                **book_price_data  # Merge in all price statistics
            }
            
            # Add metadata from books.json
            if book_meta:
                merged_book['isbns'] = [list(item.keys())[0] for item in book_meta]
                
                # Get metadata from first ISBN
                if book_meta:
                    first_isbn_key = list(book_meta[0].keys())[0]
                    meta = book_meta[0][first_isbn_key]
                    merged_book['authors'] = meta.get('authors', [])
                    merged_book['icon_url'] = meta.get('icon_url', '')
                    merged_book['icon_path'] = meta.get('icon_path', '')
              # Add to appropriate grade
            grade = merged_book['assigned_grade']
            if grade in merged_data['books_by_grade']:
                merged_data['books_by_grade'][grade].append(merged_book)
                # Debug logging for problematic grades
                if grade in ['Kindergarten', '4th Grade', '5th Grade', '6th Grade']:
                    logger.info(f"Added book '{title}' to {grade}")
            else:
                merged_data['books_by_grade']['Unassigned'].append(merged_book)
                logger.warning(f"Book '{title}' assigned to Unassigned because grade '{grade}' not found")
            
            merged_data['total_books'] += 1
        
        return jsonify({
            'success': True,
            'data': merged_data
        })
        
    except Exception as e:
        logger.error(f"Error in dashboard data API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Image Management Routes
@app.route("/api/images/<isbn>")
def get_isbn_images(isbn):
    """Get existing images for an ISBN"""
    try:
        from scripts.image_downloader import get_existing_image_info
        images = get_existing_image_info(isbn)
        return jsonify({"isbn": isbn, "images": images})
    except Exception as e:
        logger.error(f"Error getting images for ISBN {isbn}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/images/<isbn>/<source>", methods=["POST"])
def download_image_for_isbn(isbn, source):
    """Download image for ISBN from specific source"""
    try:
        from scripts.image_downloader import download_image_for_isbn_source
        
        # Get the URL for this ISBN and source from price data
        df = load_prices_data()
        if df.empty:
            return jsonify({"error": "No price data available"}), 404
            
        # Find the most recent successful record for this ISBN and source
        isbn_source_data = df[(df["isbn"] == isbn) & (df["source"].str.lower() == source.lower())]
        if isbn_source_data.empty:
            return jsonify({"error": f"No data found for ISBN {isbn} and source {source}"}), 404
            
        # Get the most recent record with a URL
        recent_data = isbn_source_data[isbn_source_data["url"].notna() & (isbn_source_data["url"] != "")]
        if recent_data.empty:
            return jsonify({"error": f"No URL found for ISBN {isbn} and source {source}"}), 404
            
        latest_record = recent_data.sort_values("timestamp", ascending=False).iloc[0]
        url = latest_record["url"]
        
        # Download the image
        result = download_image_for_isbn_source(isbn, source, url)
        
        if result["success"]:
            return jsonify({
                "message": f"Image downloaded successfully for {isbn} from {source}",
                "result": result
            })
        else:
            return jsonify({
                "error": f"Failed to download image: {result.get('error', 'Unknown error')}",
                "result": result
            }), 400
            
    except Exception as e:
        logger.error(f"Error downloading image for ISBN {isbn} from {source}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/images/cleanup", methods=["POST"])
def cleanup_images():
    """Clean up old image files"""
    try:
        from scripts.image_downloader import cleanup_old_images
        
        days_old = request.json.get("days_old", 30) if request.json else 30
        result = cleanup_old_images(days_old)
        
        if result["success"]:
            return jsonify({
                "message": f"Cleanup completed. Deleted {result['deleted_count']} files.",
                "result": result
            })
        else:
            return jsonify({
                "error": f"Cleanup failed: {result.get('error', 'Unknown error')}",
                "result": result
            }), 500
            
    except Exception as e:
        logger.error(f"Error during image cleanup: {e}")
        return jsonify({"error": str(e)}), 500


# --- Grade Level Book Grouping API ---

# Helper to load grades.json
def load_grades() -> dict[str, list[str]]:
    if not GRADES_FILE.exists():
        return {}
    with open(GRADES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# Helper to save grades.json
def save_grades(grades: dict[str, list[str]]):
    with open(GRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(grades, f, indent=2)

# Helper to load books.json
def load_books():
    books_file = BASE_DIR / "books.json"
    if not books_file.exists():
        return {}
    with open(books_file, "r", encoding="utf-8") as f:
        return json.load(f)

@app.route("/api/grades", methods=["GET"])
def get_grades():
    """Get all grade groupings"""
    try:
        grades = load_grades()
        return jsonify(grades)
    except Exception as e:
        logger.error(f"Error loading grades: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/grades/add", methods=["POST"])
def add_book_to_grade():
    """Add a book to a grade level"""
    try:
        data = request.json or {}
        grade = data.get("grade")
        book = data.get("book")
        if not grade or not book:
            return jsonify({"error": "Missing grade or book"}), 400
        with grade_db_lock:
            grades = load_grades()
            books = load_books()
            if book not in books:
                return jsonify({"error": "Book not found in books.json"}), 404
            if grade not in grades:
                grades[grade] = []
            if book in grades[grade]:
                return jsonify({"error": "Book already in grade"}), 400
            grades[grade].append(book)
            save_grades(grades)
        return jsonify({"message": f"Added '{book}' to {grade}"})
    except Exception as e:
        logger.error(f"Error adding book to grade: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/grades/remove", methods=["POST"])
def remove_book_from_grade():
    """Remove a book from a grade level"""
    try:
        data = request.json or {}
        grade = data.get("grade")
        book = data.get("book")
        if not grade or not book:
            return jsonify({"error": "Missing grade or book"}), 400
        with grade_db_lock:
            grades = load_grades()
            if grade not in grades or book not in grades[grade]:
                return jsonify({"error": "Book not in grade"}), 404
            grades[grade].remove(book)
            save_grades(grades)
        return jsonify({"message": f"Removed '{book}' from {grade}"})
    except Exception as e:
        logger.error(f"Error removing book from grade: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/grades/remove_all", methods=["POST"])
def remove_book_from_all_grades():
    """Remove a book from all grades"""
    try:
        data = request.json or {}
        book = data.get("book")
        if not book:
            return jsonify({"error": "Missing book"}), 400
        with grade_db_lock:
            grades = load_grades()
            found = False
            for grade in grades:
                if book in grades[grade]:
                    grades[grade].remove(book)
                    found = True
            if not found:
                return jsonify({"error": "Book not found in any grade"}), 404
            save_grades(grades)
        return jsonify({"message": f"Removed '{book}' from all grades"})
    except Exception as e:
        logger.error(f"Error removing book from all grades: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/grades/move", methods=["POST"])
def move_book_to_grade():
    """Remove a book from all grades and add to a given grade"""
    try:
        data = request.json or {}
        grade = data.get("grade")
        book = data.get("book")
        if not grade or not book:
            return jsonify({"error": "Missing grade or book"}), 400
        with grade_db_lock:
            grades = load_grades()
            books = load_books()
            if book not in books:
                return jsonify({"error": "Book not found in books.json"}), 404
            # Remove from all grades
            for g in grades:
                if book in grades[g]:
                    grades[g].remove(book)
            # Add to new grade
            if grade not in grades:
                grades[grade] = []
            if book not in grades[grade]:
                grades[grade].append(book)
            save_grades(grades)
        return jsonify({"message": f"Moved '{book}' to {grade}"})
    except Exception as e:
        logger.error(f"Error moving book to grade: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/books/manual", methods=["POST"])
def add_book_manual():
    """Add a book manually with custom metadata"""
    try:
        data = request.json or {}
        title = data.get("title", "").strip()
        authors_data = data.get("authors", [])
        isbns = data.get("isbns", [])
        icon_url = data.get("icon_url", "").strip()
        publisher = data.get("publisher", "").strip()
        year = data.get("year", "").strip()
        grade = data.get("grade", "").strip()

        # Handle authors - can be string or list
        if isinstance(authors_data, list):
            authors_str = ", ".join(authors_data)
        else:
            authors_str = str(authors_data).strip()

        # Validation
        if not title:
            return jsonify({"error": "Title is required"}), 400
        
        if not isbns or len(isbns) == 0:
            return jsonify({"error": "At least one ISBN is required"}), 400

        # Clean and validate ISBNs
        clean_isbns = []
        for isbn in isbns:
            isbn = isbn.strip().replace("-", "").replace(" ", "")
            if isbn and len(isbn) in [10, 13]:
                clean_isbns.append(isbn)
            elif isbn:  # Non-empty but invalid
                return jsonify({"error": f"Invalid ISBN format: {isbn}"}), 400
        
        if not clean_isbns:
            return jsonify({"error": "No valid ISBNs provided"}), 400

        # Parse authors
        authors = []
        if authors_str:
            authors = [author.strip() for author in authors_str.split(",") if author.strip()]

        books_file = BASE_DIR / "books.json"
        books = json.loads(books_file.read_bytes()) if books_file.exists() else {}

        # Check if any ISBN is already tracked
        for isbn in clean_isbns:
            for book_title, isbn_list in books.items():
                for item in isbn_list:
                    if isbn in item:
                        return jsonify({"error": f"ISBN {isbn} is already tracked under '{book_title}'"}), 400

        # Create book entry
        isbn_list = books.setdefault(title, [])            # Add each ISBN with the same metadata
        for isbn in clean_isbns:
            isbn_metadata = {
                "title": title,
                "isbn13": isbn if len(isbn) == 13 else "",
                "isbn10": isbn if len(isbn) == 10 else "",
                "authors": authors,
                "publisher": publisher,
                "year": year,
                "source": "manual",
                "notes": "",
                "icon_url": icon_url
            }
            
            # Download icon if URL is provided
            if icon_url:
                try:
                    from scripts.image_downloader import download_googlebooks_icon
                    download_result = download_googlebooks_icon(isbn, icon_url)
                    if download_result["success"]:
                        # Add the local path to the metadata
                        isbn_metadata["icon_path"] = download_result["image_path"]
                        logger.info(f"Downloaded icon for manually added ISBN {isbn}")
                except Exception as e:
                    logger.warning(f"Failed to download icon for manually added ISBN {isbn}: {e}")
            
            isbn_list.append({isbn: isbn_metadata})

        # Save to file
        books_file.write_text(json.dumps(books, indent=4))
        logger.info(f"Manually added '{title}' with {len(clean_isbns)} ISBN(s): {', '.join(clean_isbns)}")

        # Assign to grade level if specified
        if grade:
            try:
                with grade_db_lock:
                    grades = load_grades()
                    if grade not in grades:
                        grades[grade] = []
                    if title not in grades[grade]:
                        grades[grade].append(title)
                        save_grades(grades)
                        logger.info(f"Assigned '{title}' to {grade}")
            except Exception as e:
                logger.error(f"Error assigning book to grade: {e}")
                # Don't fail the entire operation if grade assignment fails

        isbn_count = len(clean_isbns)
        if isbn_count == 1:
            return jsonify({"message": f"Manually added '{title}' with ISBN {clean_isbns[0]}"})
        else:
            return jsonify({"message": f"Manually added '{title}' with {isbn_count} ISBNs"})

    except Exception as e:
        logger.error(f"Error manually adding book: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/books/<title>/<isbn>", methods=["PUT", "PATCH"])
def update_isbn_metadata(title, isbn):
    """Update metadata for a specific ISBN under a book title"""
    try:
        books_file = BASE_DIR / "books.json"
        if not books_file.exists():
            return jsonify({"error": "No books file found"}), 404
        books = json.loads(books_file.read_bytes())
        if title not in books:
            return jsonify({"error": "Book title not found"}), 404
        isbn_list = books[title]
        found = False
        for item in isbn_list:
            if isbn in item:
                found = True
                metadata = item[isbn]
                data = request.json or {}
                # Only update allowed fields
                for field in ["title", "authors", "publisher", "year", "icon_url", "notes"]:
                    if field in data:
                        metadata[field] = data[field]
                # If authors is a string, convert to list
                if isinstance(metadata.get("authors"), str):
                    metadata["authors"] = [a.strip() for a in metadata["authors"].split(",") if a.strip()]
                break
        if not found:
            return jsonify({"error": "ISBN not found"}), 404
        books_file.write_text(json.dumps(books, indent=4))
        return jsonify({"message": f"ISBN {isbn} updated for {title}"})
    except Exception as e:
        logger.error(f"Error updating ISBN: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/images/download-all-icons", methods=["POST"])
def download_all_icons():
    """Download all book icons from Google Books to local storage"""
    try:
        from scripts.image_downloader import download_all_book_icons
        
        # Load books data
        books_file = BASE_DIR / "books.json"
        if not books_file.exists():
            return jsonify({"error": "No books file found"}), 404
            
        books = json.loads(books_file.read_bytes())
        
        # Download all icons
        result = download_all_book_icons(books)
        
        # Save updated book data with icon paths
        if result["success"] and (result["downloaded"] > 0 or result["already_local"] > 0):
            books_file.write_text(json.dumps(books, indent=4))
            logger.info(f"Updated books.json with local icon paths for {result['downloaded']} books")
        
        return jsonify({
            "message": f"Downloaded {result['downloaded']} icons, {result['already_local']} already local, {result['failed']} failed",
            "result": result
        })
            
    except Exception as e:
        logger.error(f"Error downloading all icons: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/images/<isbn>/googlebooks", methods=["POST"])
def download_googlebooks_icon_api(isbn):
    """Download a Google Books icon from a URL"""
    try:
        from scripts.image_downloader import download_googlebooks_icon
        
        data = request.json or {}
        url = data.get("url", "")
        
        if not url:
            return jsonify({"error": "URL is required"}), 400
            
        # Download the icon
        result = download_googlebooks_icon(isbn, url)
        
        if not result["success"]:
            return jsonify({
                "error": f"Failed to download image: {result.get('error', 'Unknown error')}",
                "result": result
            }), 400
            
        # Update icon_path in books.json if download was successful
        books_file = BASE_DIR / "books.json"
        if books_file.exists():
            books = json.loads(books_file.read_bytes())
            # Find the ISBN in the books data
            for title, isbn_list in books.items():
                for item in isbn_list:
                    if isbn in item:
                        item[isbn]["icon_path"] = result["image_path"]
                        # Save the updated books data
                        books_file.write_text(json.dumps(books, indent=4))
                        logger.info(f"Updated books.json with local icon path for ISBN {isbn}")
                        break
        
        return jsonify({
            "message": f"Image downloaded successfully for {isbn} from Google Books",
            "result": result
        })
            
    except Exception as e:
        logger.error(f"Error downloading Google Books icon for ISBN {isbn}: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    logger.info("Starting Book Price Tracker Flask app")

    # Create sample data if needed
    create_sample_data()

    # Run the app
    app.run(debug=True, host="0.0.0.0", port=5000)
