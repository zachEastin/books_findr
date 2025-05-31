"""
Book Price Tracker - Flask Web Application
Main entry point for the web interface
"""

from flask import Flask, render_template, jsonify, request
import pandas as pd
import os
from datetime import datetime
import logging
from pathlib import Path

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


def load_prices_data():
    """Load prices data from CSV file"""
    try:
        if PRICES_CSV.exists():
            df = pd.read_csv(PRICES_CSV)
            logger.info(f"Loaded {len(df)} price records from CSV")
            return df
        else:
            logger.warning("prices.csv not found, creating empty DataFrame")
            # Create empty DataFrame with expected columns
            df = pd.DataFrame(columns=["timestamp", "isbn", "title", "source", "price", "url", "notes"])
            return df
    except Exception as e:
        logger.error(f"Error loading prices data: {e}")
        return pd.DataFrame(columns=["timestamp", "isbn", "title", "source", "price", "url", "notes"])


def create_sample_data():
    """Create sample data if CSV doesn't exist"""
    if not PRICES_CSV.exists():
        sample_data = [
            {
                "timestamp": datetime.now().isoformat(),
                "isbn": "9780134685991",
                "title": "Effective Java",
                "source": "BookScouter",
                "price": 45.99,
                "url": "https://bookscouter.com/prices/9780134685991",
                "notes": "Sample data",
            },
            {
                "timestamp": datetime.now().isoformat(),
                "isbn": "9780134685991",
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

            # Get unique ISBNs
            unique_isbns = df["isbn"].unique().tolist()

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
            unique_isbns = []
            charts = {}

        return render_template(
            "index.html", prices=prices_data, isbns=unique_isbns, total_records=len(df), charts=charts
        )

    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return render_template("index.html", prices=[], isbns=[], total_records=0, charts={}, error=str(e))


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


@app.route("/api/isbns")
def get_isbns():
    """Get list of ISBNs being tracked"""
    try:
        isbn_file = BASE_DIR / "isbns.txt"
        if isbn_file.exists():
            with open(isbn_file, "r") as f:
                isbns = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
            return jsonify({"isbns": isbns, "count": len(isbns)})
        return jsonify({"isbns": [], "count": 0})
    except Exception as e:
        logger.error(f"Error loading ISBNs: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/isbns", methods=["POST"])
def add_isbn():
    """Add a new ISBN to track"""
    try:
        data = request.json
        isbn = data.get("isbn", "").strip()

        if not isbn:
            return jsonify({"error": "ISBN is required"}), 400

        # Validate ISBN format (basic check)
        if not isbn.replace("-", "").isdigit() or len(isbn.replace("-", "")) not in [10, 13]:
            return jsonify({"error": "Invalid ISBN format"}), 400

        isbn_file = BASE_DIR / "isbns.txt"

        # Check if ISBN already exists
        existing_isbns = []
        if isbn_file.exists():
            with open(isbn_file, "r") as f:
                existing_isbns = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

        if isbn in existing_isbns:
            return jsonify({"error": "ISBN already being tracked"}), 400

        # Add ISBN to file
        with open(isbn_file, "a") as f:
            f.write(f"\n{isbn}")

        logger.info(f"Added new ISBN: {isbn}")
        return jsonify({"message": f"ISBN {isbn} added successfully"})

    except Exception as e:
        logger.error(f"Error adding ISBN: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/isbns/<isbn>", methods=["DELETE"])
def remove_isbn(isbn):
    """Remove an ISBN from tracking"""
    try:
        isbn_file = BASE_DIR / "isbns.txt"

        if not isbn_file.exists():
            return jsonify({"error": "No ISBNs file found"}), 404

        # Read all ISBNs
        with open(isbn_file, "r") as f:
            lines = f.readlines()

        # Filter out the ISBN to remove
        filtered_lines = []
        isbn_removed = False

        for line in lines:
            if line.strip() == isbn:
                isbn_removed = True
                continue
            filtered_lines.append(line)

        if not isbn_removed:
            return jsonify({"error": "ISBN not found"}), 404

        # Write back to file
        with open(isbn_file, "w") as f:
            f.writelines(filtered_lines)

        logger.info(f"Removed ISBN: {isbn}")
        return jsonify({"message": f"ISBN {isbn} removed successfully"})

    except Exception as e:
        logger.error(f"Error removing ISBN: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/scrape/<isbn>", methods=["POST"])
def trigger_scrape(isbn):
    """Trigger scraping for a specific ISBN"""
    try:
        from scripts.scraper import scrape_all_sources, save_results_to_csv

        logger.info(f"Manual scrape triggered for ISBN: {isbn}")
        results = scrape_all_sources(isbn)

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


if __name__ == "__main__":
    logger.info("Starting Book Price Tracker Flask app")

    # Create sample data if needed
    create_sample_data()

    # Run the app
    app.run(debug=True, host="127.0.0.1", port=5000)
