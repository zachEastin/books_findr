"""
Book Price Tracker - Logging Configuration
Centralized logging setup with rotation and multiple handlers
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
import sys

# Get the base directory
BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with both file and console handlers

    Args:
        name: Logger name (usually __name__)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # File handler with rotation (max 10MB, keep 5 files)
    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / f"{name.replace('.', '_')}.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def setup_scraper_logger() -> logging.Logger:
    """Set up logger specifically for scraping operations"""
    return setup_logger("scraper", logging.INFO)


def setup_scheduler_logger() -> logging.Logger:
    """Set up logger specifically for scheduling operations"""
    return setup_logger("scheduler", logging.INFO)


def setup_app_logger() -> logging.Logger:
    """Set up logger specifically for Flask app"""
    return setup_logger("app", logging.INFO)


def log_scrape_result(
    logger: logging.Logger, isbn: str, source: str, success: bool, price: float = None, error: str = None
):
    """
    Log the result of a scraping operation

    Args:
        logger: Logger instance
        isbn: The ISBN that was scraped
        source: The source website
        success: Whether scraping was successful
        price: The price found (if successful)
        error: Error message (if failed)
    """
    if success:
        logger.info(f"[SUCCESS] Successfully scraped {source} for ISBN {isbn}: ${price}")
    else:
        logger.error(f"[FAILED] Failed to scrape {source} for ISBN {isbn}: {error}")


def log_task_start(logger: logging.Logger, task_name: str):
    """Log the start of a task"""
    logger.info(f"[START] Starting task: {task_name}")


def log_task_complete(logger: logging.Logger, task_name: str, duration_seconds: float = None):
    """Log the completion of a task"""
    if duration_seconds:
        logger.info(f"[COMPLETE] Completed task: {task_name} (took {duration_seconds:.2f}s)")
    else:
        logger.info(f"[COMPLETE] Completed task: {task_name}")


def log_task_error(logger: logging.Logger, task_name: str, error: str):
    """Log an error in a task"""
    logger.error(f"[ERROR] Task failed: {task_name} - {error}")


# Create default loggers
scraper_logger = setup_scraper_logger()
scheduler_logger = setup_scheduler_logger()
app_logger = setup_app_logger()


if __name__ == "__main__":
    # Test the logging setup
    test_logger = setup_logger("test")
    test_logger.info("Testing logging setup")
    test_logger.warning("This is a warning")
    test_logger.error("This is an error")

    # Test scrape logging
    log_scrape_result(test_logger, "9780134685991", "Christianbook", False, error="Connection timeout")

    print(f"Log files created in: {LOGS_DIR}")
