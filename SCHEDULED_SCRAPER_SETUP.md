# Scheduled Scraper Setup Guide

## Overview
This guide will help you set up automatic daily scraping of book prices using Windows Task Scheduler.

## Files Created
- `scheduled_scraper.py` - Standalone Python script for scheduled execution
- `run_scheduled_scraper.bat` - Windows batch file to run the scraper
- `SCHEDULED_SCRAPER_SETUP.md` - This setup guide

## Prerequisites

### Virtual Environment Setup
**IMPORTANT**: This project requires a Python virtual environment to work properly with Task Scheduler.

1. **Create Virtual Environment** (if not already done):
   ```powershell
   cd "t:\Coding_Projects\BooksFindr\books_findr"
   python -m venv venv
   ```

2. **Activate Virtual Environment**:
   ```powershell
   venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Verify Installation**:
   ```powershell
   python -c "import asyncio, aiohttp, bs4, pandas; print('All dependencies available')"
   ```

## Quick Setup Steps

### 1. Test the Scheduler
First, test that everything is working with the virtual environment:

```powershell
cd "t:\Coding_Projects\BooksFindr\books_findr"
venv\Scripts\activate
python scheduled_scraper.py --test
```

### 2. Manual Test Run
Test a full scraping run using the batch file (which handles venv activation):

```powershell
.\run_scheduled_scraper.bat
```

This batch file will:
- Activate the virtual environment automatically
- Verify all dependencies are available
- Run the scheduled scraper
- Provide clear error messages if anything fails

### 3. Set Up Windows Task Scheduler

#### Option A: Using PowerShell Script (Recommended)
Run the automated setup script:

```powershell
# Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup_task_scheduler.ps1

# Or specify a custom time (24-hour format)
.\setup_task_scheduler.ps1 -Time "08:30"
```

#### Option B: Using Task Scheduler GUI
1. Press `Win + R`, type `taskschd.msc`, press Enter
2. Click "Create Basic Task..." in the right panel
3. **Name**: `Book Price Tracker Daily Scrape`
4. **Description**: `Daily scraping of book prices for BooksFindr`
5. **Trigger**: Daily
6. **Start Time**: Choose your preferred time (recommended: 6:00 AM)
7. **Action**: Start a program
8. **Program**: `t:\Coding_Projects\BooksFindr\books_findr\run_scheduled_scraper.bat`
9. **Start in**: `t:\Coding_Projects\BooksFindr\books_findr`
10. Click Finish

#### Option C: Using PowerShell (Advanced)
```powershell
# Create a new scheduled task
$action = New-ScheduledTaskAction -Execute "t:\Coding_Projects\BooksFindr\books_findr\run_scheduled_scraper.bat" -WorkingDirectory "t:\Coding_Projects\BooksFindr\books_findr"
$trigger = New-ScheduledTaskTrigger -Daily -At "06:00"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U

Register-ScheduledTask -TaskName "Book Price Tracker Daily Scrape" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Daily scraping of book prices for BooksFindr"
```

## Configuration Options

### Changing Schedule Time
- Edit the trigger time in Task Scheduler
- Or modify the PowerShell command above with your preferred time

### Logging
- All scheduled runs are logged to: `logs/scheduled_scraper.log`
- Regular scraper logs go to: `logs/scraper.log`
- App logs go to: `logs/app.log`

### Troubleshooting

#### Common Issues:

1. **"Module not found" errors**
   - Make sure you're running from the correct directory
   - Check that all Python dependencies are installed: `pip install -r requirements.txt`

2. **"No ISBNs found"**
   - Ensure `isbns.json` exists and contains ISBN data
   - Add ISBNs through the web interface at `http://127.0.0.1:5000/admin`

3. **Task doesn't run**
   - Check Task Scheduler History
   - Verify the batch file path is correct
   - Ensure the user account has proper permissions

4. **Python not found**
   - Make sure Python is in your system PATH
   - Or edit the batch file to use full Python path: `"C:\Python\python.exe" scheduled_scraper.py`

#### Testing Commands:

```powershell
# Test the scheduler setup
python scheduled_scraper.py --test

# Test a full run
python scheduled_scraper.py

# Test the batch file
.\run_scheduled_scraper.bat

# Check recent log entries
Get-Content .\logs\scheduled_scraper.log -Tail 20
```

## Monitoring

### Check Last Run
```powershell
# View recent scheduled scraper logs
Get-Content .\logs\scheduled_scraper.log -Tail 50

# Check if task is scheduled
Get-ScheduledTask -TaskName "Book Price Tracker Daily Scrape"

# View task history (requires admin)
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-TaskScheduler/Operational'; ID=201} | Where-Object {$_.Message -like "*Book Price Tracker*"} | Select-Object TimeCreated, Message
```

### Log Rotation
The log files will grow over time. Consider setting up log rotation or periodically archiving old logs.

## Security Notes
- The task runs with your user account privileges
- Ensure your system is secure if running automatically
- Consider using a dedicated service account for production setups

## Customization

### Different Schedule Patterns
You can modify the trigger for different patterns:
- Multiple times per day: Add multiple triggers
- Weekdays only: Use weekly trigger with specific days
- Monthly: Use monthly trigger

### Error Notifications
To get notified of failures, you can:
1. Set up email notifications in Task Scheduler (Enterprise versions)
2. Add email sending to the Python script
3. Use Windows Event Log and set up alerts

## Files and Directories
```
t:\Coding_Projects\BooksFindr\books_findr\
├── scheduled_scraper.py          # Main scheduler script
├── run_scheduled_scraper.bat     # Batch file for Task Scheduler
├── logs/
│   ├── scheduled_scraper.log     # Scheduled run logs
│   ├── scraper.log              # Scraper process logs
│   └── app.log                  # Flask app logs
├── scripts/
│   └── scraper.py               # Core scraping logic
└── isbns.json                   # ISBNs to track
```

Ready to set up your scheduled scraping! 🚀
