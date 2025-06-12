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
            df = pd.read_csv(PRICES_CSV, dtype={'isbn': str})
            logger.info(f"Loaded {len(df)} price records from CSV")
            return df
        else:
            logger.warning("prices.csv not found, creating empty DataFrame")
            # Create empty DataFrame with expected columns
            df = pd.DataFrame(columns=["timestamp", "isbn", "book_title", "title", "source", "price", "url", "notes"])
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
                "source": "BookScouter",
                "price": 45.99,
                "url": "https://bookscouter.com/prices/9780134685991",
                "notes": "Sample data",
            },
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
            return jsonify({"error": "ISBN already tracked"}), 400

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
                metadata_result["source"] = "google_books"
                # Try to fetch Google Books thumbnail/icon
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
        if isbn_input:
            result = asyncio.run(process_isbn(isbn_input))
            # If title was not provided, try to get it from metadata
            if not original_title:
                title_from_metadata = result["metadata"].get("title") if result["metadata"] else None
                if title_from_metadata:
                    title = title_from_metadata.strip()
                    # Move the ISBN under the derived title in books.json
                    isbn_list = books.setdefault(title, [])
                else:
                    title = isbn_input  # fallback to ISBN as title
                    isbn_list = books.setdefault(title, [])
            if result["success"]:
                isbn_list.append({isbn_input: result["metadata"]})
                added = 1
            else:
                return jsonify({"error": result["error"]}), 400
        else:
            # Require author if adding by title only
            if not author:
                return jsonify({"error": "Author is required when adding by title"}), 400
            google_books_api = GoogleBooksAPI()
            search_results = google_books_api.search_by_title_and_author(title, author=author, max_results=5)
            if not search_results:
                return jsonify({"error": "No ISBNs found for title and author"}), 404
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
            
            return jsonify({"message": f"Added {added} ISBN(s)"})
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

        # Convert to list of dictionaries
        records = df_recent.to_dict("records")
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
            latest_by_source_isbn = book_data_sorted.groupby(["source", "isbn"]).first().reset_index()            # Get valid prices from most recent records
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


if __name__ == "__main__":
    logger.info("Starting Book Price Tracker Flask app")

    # Create sample data if needed
    create_sample_data()

    # Run the app
    app.run(debug=True, host="127.0.0.1", port=5000)
