# Book Price Tracker

A local Python app that tracks book prices across various retailers using ISBNs. Scrapes BookScouter, Christianbook, RainbowResource, AbeBooks, and pulls pricing history graphs from CamelCamelCamel. Data is stored in CSV and updated daily.

## Features

- Daily price scraping and storage
- Tracks BookScouter, Christianbook.com, RainbowResource.com, AbeBooks.com
- CamelCamelCamel graph integration
- Visual UI using Flask and Material Design
- CSV-based data tracking
- Logs activity and scraping errors

## Tech Stack

- Python 3.12+
- Flask (for UI)
- Pandas (for CSV data)
- Selenium or Playwright (for scraping)
- Schedule (for daily jobs)
- MaterializeCSS or equivalent (for UI theming)

## Setup

```bash
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Running

```bash
python app.py  # Start the UI
python scripts/scheduler.py  # Run scraping & data update loop
```

## Directory Layout

```
book-price-tracker/
├── data/             # Stores CSV files
├── scripts/          # Scraper, logger, and scheduler
├── static/           # UI CSS
├── templates/        # Flask HTML templates
├── app.py            # Web app entry point
├── requirements.txt
└── README.md
```