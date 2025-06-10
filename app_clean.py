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
            # Load with ISBN as string to avoid integer conversion
            df = pd.read_csv(PRICES_CSV, dtype={'isbn': str})
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
            
            # Get book title - prioritize metadata over price data
            title = "Unknown Title"
            try:
                isbn_metadata = json.loads((BASE_DIR / "isbns.json").read_bytes())
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
                    "success": str(row["success"]) if pd.notna(row["success"]) else "False",
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


if __name__ == "__main__":
    logger.info("Starting Book Price Tracker Flask app")

    # Create sample data if needed
    create_sample_data()

    # Run the app
    app.run(debug=True, host="127.0.0.1", port=5000)
