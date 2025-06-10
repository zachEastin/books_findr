@echo off
REM Book Price Tracker - Scheduled Scraper Batch File
REM This batch file runs the scheduled scraper and handles errors

echo Starting Book Price Tracker Scheduled Scraper...
echo.

REM Change to the project directory
cd /d "t:\Coding_Projects\BooksFindr\books_findr"

REM Check if we're in the right directory
if not exist "scheduled_scraper.py" (
    echo ERROR: Cannot find scheduled_scraper.py in current directory
    echo Current directory: %CD%
    echo Please check the path in this batch file
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Cannot find virtual environment at venv\Scripts\activate.bat
    echo Please ensure the virtual environment is set up correctly
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Verify activation by checking if Python can import required modules
echo Verifying virtual environment setup...
python -c "import asyncio, aiohttp, bs4, pandas; print('Virtual environment ready')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Required Python packages not found in virtual environment
    echo Please run: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Run the Python scraper
echo Running scheduled scraper...
python scheduled_scraper.py

REM Check the exit code
if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Scheduled scraping completed successfully
) else (
    echo.
    echo ERROR: Scheduled scraping failed with exit code %ERRORLEVEL%
    echo Check the logs at: logs\scheduled_scraper.log
)

REM Uncomment the line below if you want to see the output when run manually
REM pause

exit /b %ERRORLEVEL%
