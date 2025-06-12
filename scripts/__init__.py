"""
Book Price Tracker Scripts Package
"""

from .logger import setup_logger, scraper_logger, scheduler_logger, app_logger
from .scraper import (
    scrape_all_isbns,
    scrape_all_sources,
    load_isbns_from_file,
    save_results_to_csv,
    initialize_chromedriver_session,  # New session management function
    # Async versions
    scrape_all_isbns_async,
    scrape_multiple_isbns,
    scrape_all_sources_async,
    scrape_christianbook_async,
    scrape_rainbowresource_async,
    scrape_abebooks_async,
    scrape_camelcamelcamel_async,
    # Sync versions (for backward compatibility)
    scrape_christianbook,
    scrape_rainbowresource,
    scrape_abebooks,
    scrape_camelcamelcamel,
)
from .scheduler import start_price_tracking, stop_price_tracking, price_scheduler

__all__ = [
    "setup_logger",
    "scraper_logger",
    "scheduler_logger",
    "app_logger",
    "scrape_all_isbns",
    "scrape_all_sources",
    "load_isbns_from_file",
    "save_results_to_csv",
    "initialize_chromedriver_session",  # New session management function
    # Async versions
    "scrape_all_isbns_async",
    "scrape_multiple_isbns",
    "scrape_all_sources_async",
    "scrape_christianbook_async",
    "scrape_rainbowresource_async",
    "scrape_abebooks_async",
    "scrape_camelcamelcamel_async",
    # Sync versions (for backward compatibility)
    "scrape_christianbook",
    "scrape_rainbowresource",
    "scrape_abebooks",
    "scrape_camelcamelcamel",
    "start_price_tracking",
    "stop_price_tracking",
    "price_scheduler",
]
