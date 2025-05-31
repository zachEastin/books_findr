"""
Book Price Tracker - Scheduling Module
Handles daily automation of scraping tasks
"""

import schedule
import time
from datetime import datetime, timedelta
import threading
from pathlib import Path

from .logger import scheduler_logger, log_task_start, log_task_complete, log_task_error
from .scraper import scrape_all_isbns


# Configuration
DEFAULT_SCRAPE_TIME = "09:00"  # 9 AM daily


class PriceTrackingScheduler:
    """Manages scheduled tasks for price tracking"""

    def __init__(self):
        self.running = False
        self.thread = None
        self.last_run = None

    def schedule_daily_scraping(self, time_str: str = DEFAULT_SCRAPE_TIME):
        """
        Schedule daily scraping at specified time

        Args:
            time_str: Time in HH:MM format (24-hour)
        """
        schedule.clear()  # Clear any existing schedules

        schedule.every().day.at(time_str).do(self._run_daily_scrape_job)

        scheduler_logger.info(f"Scheduled daily scraping at {time_str}")

    def _run_daily_scrape_job(self):
        """Execute the daily scraping job"""
        log_task_start(scheduler_logger, "Daily scraping job")
        start_time = time.time()

        try:
            # Run the scraping
            scrape_all_isbns()

            # Update last run time
            self.last_run = datetime.now()

            end_time = time.time()
            duration = end_time - start_time
            log_task_complete(scheduler_logger, "Daily scraping job", duration)

        except Exception as e:
            log_task_error(scheduler_logger, "Daily scraping job", str(e))

    def start_scheduler(self):
        """Start the scheduler in a background thread"""
        if self.running:
            scheduler_logger.warning("Scheduler is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()

        scheduler_logger.info("Scheduler started successfully")

    def stop_scheduler(self):
        """Stop the scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

        scheduler_logger.info("Scheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)  # Check every second
            except Exception as e:
                scheduler_logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)  # Wait a minute before retrying

    def get_next_run_time(self) -> str:
        """Get the next scheduled run time"""
        jobs = schedule.jobs
        if jobs:
            next_run = min(job.next_run for job in jobs)
            return next_run.strftime("%Y-%m-%d %H:%M:%S")
        return "No jobs scheduled"

    def get_last_run_time(self) -> str:
        """Get the last run time"""
        if self.last_run:
            return self.last_run.strftime("%Y-%m-%d %H:%M:%S")
        return "Never"

    def force_run_now(self):
        """Force run the scraping job immediately"""
        scheduler_logger.info("Force running scraping job")
        self._run_daily_scrape_job()

    def get_status(self) -> dict:
        """Get scheduler status information"""
        return {
            "running": self.running,
            "next_run": self.get_next_run_time(),
            "last_run": self.get_last_run_time(),
            "scheduled_jobs": len(schedule.jobs),
        }


# Global scheduler instance
price_scheduler = PriceTrackingScheduler()


def start_price_tracking(scrape_time: str = DEFAULT_SCRAPE_TIME):
    """
    Start the price tracking scheduler

    Args:
        scrape_time: Time to run daily scrapes (HH:MM format)
    """
    try:
        price_scheduler.schedule_daily_scraping(scrape_time)
        price_scheduler.start_scheduler()

        scheduler_logger.info(f"Price tracking started - next run: {price_scheduler.get_next_run_time()}")

    except Exception as e:
        log_task_error(scheduler_logger, "Starting price tracking", str(e))


def stop_price_tracking():
    """Stop the price tracking scheduler"""
    try:
        price_scheduler.stop_scheduler()
        scheduler_logger.info("Price tracking stopped")
    except Exception as e:
        log_task_error(scheduler_logger, "Stopping price tracking", str(e))


def run_interactive_scheduler():
    """
    Run an interactive scheduler that accepts commands
    Useful for testing and manual control
    """
    print("Book Price Tracker - Interactive Scheduler")
    print("Commands:")
    print("  start [time] - Start daily scheduling (default 09:00)")
    print("  stop         - Stop scheduling")
    print("  run          - Force run now")
    print("  status       - Show status")
    print("  quit         - Exit")
    print()

    while True:
        try:
            command = input("scheduler> ").strip().lower()

            if command == "quit" or command == "exit":
                break

            elif command == "status":
                status = price_scheduler.get_status()
                print(f"Running: {status['running']}")
                print(f"Next run: {status['next_run']}")
                print(f"Last run: {status['last_run']}")
                print(f"Scheduled jobs: {status['scheduled_jobs']}")

            elif command == "stop":
                stop_price_tracking()
                print("Scheduler stopped")

            elif command.startswith("start"):
                parts = command.split()
                time_str = parts[1] if len(parts) > 1 else DEFAULT_SCRAPE_TIME

                try:
                    # Validate time format
                    datetime.strptime(time_str, "%H:%M")
                    start_price_tracking(time_str)
                    print(f"Scheduler started - daily run at {time_str}")
                except ValueError:
                    print("Invalid time format. Use HH:MM (24-hour format)")

            elif command == "run":
                print("Running scraping job...")
                price_scheduler.force_run_now()
                print("Scraping job completed")

            else:
                print("Unknown command. Type 'quit' to exit.")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

    # Cleanup
    stop_price_tracking()
    print("Goodbye!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        # Run interactive mode
        run_interactive_scheduler()
    else:
        # Run in daemon mode
        try:
            print("Starting Book Price Tracker Scheduler...")
            start_price_tracking()

            print(f"Scheduler running. Next scrape: {price_scheduler.get_next_run_time()}")
            print("Press Ctrl+C to stop")

            # Keep the main thread alive
            while True:
                time.sleep(60)
                # Print status every hour
                if datetime.now().minute == 0:
                    status = price_scheduler.get_status()
                    print(f"Status - Running: {status['running']}, Next: {status['next_run']}")

        except KeyboardInterrupt:
            print("\nShutting down scheduler...")
            stop_price_tracking()
            print("Scheduler stopped. Goodbye!")
        except Exception as e:
            scheduler_logger.error(f"Scheduler error: {e}")
            stop_price_tracking()
