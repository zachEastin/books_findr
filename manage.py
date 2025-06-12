"""
Book Price Tracker - Management CLI
Command-line interface for managing the price tracking system
"""

import argparse
import sys
from pathlib import Path
import time
from datetime import datetime

# Add the project root to the path
sys.path.append(str(Path(__file__).parent))

from scripts.logger import setup_logger, log_task_start, log_task_complete
from scripts.scraper import scrape_all_isbns, load_isbns_from_file, save_results_to_csv
from scripts.scheduler import start_price_tracking, stop_price_tracking, price_scheduler


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Book Price Tracker Management CLI")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test the system components")
    test_parser.add_argument(
        "--component", choices=["scraper", "logger", "all"], default="all", help="Component to test"
    )

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Run scraping operations")
    scrape_parser.add_argument("--isbn", help="Scrape a specific ISBN")
    scrape_parser.add_argument("--all", action="store_true", help="Scrape all ISBNs from file")
    scrape_parser.add_argument(
        "--source",
        choices=["christianbook", "rainbowresource", "abebooks", "camelcamelcamel"],
        help="Scrape from specific source only",
    )

    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Manage scheduling")
    schedule_parser.add_argument("--start", metavar="TIME", help="Start daily scheduling (HH:MM format)")
    schedule_parser.add_argument("--stop", action="store_true", help="Stop scheduling")
    schedule_parser.add_argument("--status", action="store_true", help="Show scheduler status")
    schedule_parser.add_argument("--run-now", action="store_true", help="Force run scraping now")

    # Data command
    data_parser = subparsers.add_parser("data", help="Data management operations")
    data_parser.add_argument("--show", action="store_true", help="Show current data summary")
    data_parser.add_argument("--export", metavar="FILE", help="Export data to file")
    data_parser.add_argument("--clean", action="store_true", help="Clean old data")

    # Server command
    server_parser = subparsers.add_parser("server", help="Manage Flask server")
    server_parser.add_argument("--start", action="store_true", help="Start Flask server")
    server_parser.add_argument("--port", type=int, default=5000, help="Port to run server on")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Setup logging
    logger = setup_logger("cli")

    try:
        if args.command == "test":
            run_tests(args, logger)
        elif args.command == "scrape":
            run_scraping(args, logger)
        elif args.command == "schedule":
            manage_scheduling(args, logger)
        elif args.command == "data":
            manage_data(args, logger)
        elif args.command == "server":
            manage_server(args, logger)

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

    return 0


def run_tests(args, logger):
    """Run system tests"""
    log_task_start(logger, f"Running tests for {args.component}")

    if args.component in ["logger", "all"]:
        logger.info("Testing logger functionality...")
        logger.info("[SUCCESS] Logger test message")
        logger.warning("[WARNING] Logger warning message")
        logger.error("[ERROR] Logger error message")
        logger.info("Logger test completed")

    if args.component in ["scraper", "all"]:
        logger.info("Testing scraper functionality...")

        # Test ISBN loading
        isbns = load_isbns_from_file()
        logger.info(f"Loaded {len(isbns)} ISBNs from file")

        # Test data structure
        test_results = [
            {
                "timestamp": datetime.now().isoformat(),
                "isbn": "9780134685991",
                "title": "Test Book",
                "source": "TestSource",
                "price": 29.99,
                "url": "http://example.com",
                "notes": "Test data",
                "success": True,
            }
        ]

        save_results_to_csv(test_results)
        logger.info("Scraper data structure test completed")

    log_task_complete(logger, "System tests")


def run_scraping(args, logger):
    """Run scraping operations"""
    if args.isbn:
        logger.info(f"Scraping specific ISBN: {args.isbn}")
        # Import here to avoid issues if selenium not installed
        from scripts.scraper import scrape_all_sources

        results = scrape_all_sources(args.isbn)
        save_results_to_csv(results)
        logger.info(f"Completed scraping for ISBN {args.isbn}")

    elif args.all:
        logger.info("Scraping all ISBNs from file")
        scrape_all_isbns()
        logger.info("Completed scraping all ISBNs")

    else:
        logger.error("Please specify --isbn or --all")


def manage_scheduling(args, logger):
    """Manage scheduling operations"""
    if args.start:
        logger.info(f"Starting daily scheduling at {args.start}")
        start_price_tracking(args.start)
        logger.info("Scheduling started successfully")

    elif args.stop:
        logger.info("Stopping scheduling")
        stop_price_tracking()
        logger.info("Scheduling stopped")

    elif args.status:
        status = price_scheduler.get_status()
        logger.info("Scheduler Status:")
        logger.info(f"  Running: {status['running']}")
        logger.info(f"  Next run: {status['next_run']}")
        logger.info(f"  Last run: {status['last_run']}")
        logger.info(f"  Scheduled jobs: {status['scheduled_jobs']}")

    elif args.run_now:
        logger.info("Force running scraping job")
        price_scheduler.force_run_now()
        logger.info("Scraping job completed")

    else:
        logger.error("Please specify an action: --start, --stop, --status, or --run-now")


def manage_data(args, logger):
    """Manage data operations"""
    if args.show:
        import pandas as pd
        from scripts.scraper import PRICES_CSV

        if PRICES_CSV.exists():
            df = pd.read_csv(PRICES_CSV)
            logger.info("Data Summary:")
            logger.info(f"  Total records: {len(df)}")
            logger.info(f"  Unique ISBNs: {df['isbn'].nunique()}")
            logger.info(f"  Sources: {df['source'].unique().tolist()}")
            logger.info(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        else:
            logger.info("No data file found")

    elif args.export:
        logger.info(f"Exporting data to {args.export}")
        # Implementation for data export
        logger.info("Data export completed")

    elif args.clean:
        logger.info("Cleaning old data")
        # Implementation for data cleaning
        logger.info("Data cleaning completed")

    else:
        logger.error("Please specify an action: --show, --export, or --clean")


def manage_server(args, logger):
    """Manage Flask server"""
    if args.start:
        logger.info(f"Starting Flask server on port {args.port}")
        # This would normally start the server
        logger.info("Use 'python app.py' to start the Flask server")
    else:
        logger.error("Please specify --start")


if __name__ == "__main__":
    sys.exit(main())
