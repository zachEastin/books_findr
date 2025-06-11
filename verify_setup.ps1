# Verification script for scheduled scraper setup
# Run this to verify everything is working correctly

Write-Host "Book Price Tracker - Scheduled Scraper Verification" -ForegroundColor Green
Write-Host "=" * 55 -ForegroundColor Green

$projectPath = Get-Location
Write-Host "`nProject Path: $projectPath" -ForegroundColor Yellow

# Check required files
Write-Host "`n1. Checking required files..." -ForegroundColor Cyan

$requiredFiles = @(
    "scheduled_scraper.py",
    "run_scheduled_scraper.bat",
    "setup_task_scheduler.ps1",
    "books.json",
    "scripts\scraper.py"
)

$allFilesExist = $true
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "   SUCCESS: $file" -ForegroundColor Green
    } else {
        Write-Host "   ERROR: $file not found!" -ForegroundColor Red
        $allFilesExist = $false
    }
}

if (-not $allFilesExist) {
    Write-Host "`nSome required files are missing. Please check your setup." -ForegroundColor Red
    exit 1
}

# Test Python and imports
Write-Host "`n2. Testing Python setup..." -ForegroundColor Cyan
try {
    $pythonVersion = python --version 2>&1
    Write-Host "   SUCCESS: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "   ERROR: Python not found or not in PATH" -ForegroundColor Red
    exit 1
}

# Test scheduled scraper imports
Write-Host "`n3. Testing scheduled scraper..." -ForegroundColor Cyan
try {
    $testResult = python scheduled_scraper.py --test 2>&1
    if ($LASTEXITCODE -eq 0) {
        $lines = $testResult -split "`n"
        $successLines = $lines | Where-Object { $_ -match "SUCCESS:" }
        foreach ($line in $successLines) {
            Write-Host "   $line" -ForegroundColor Green
        }
    } else {
        Write-Host "   ERROR: Scheduled scraper test failed" -ForegroundColor Red
        Write-Host "   Output: $testResult" -ForegroundColor Gray
        exit 1
    }
} catch {
    Write-Host "   ERROR: Failed to run scheduled scraper test: $_" -ForegroundColor Red
    exit 1
}

# Check ISBNs
Write-Host "`n4. Checking ISBN data..." -ForegroundColor Cyan
try {
    if (Test-Path "books.json") {
        $isbnData = Get-Content "books.json" | ConvertFrom-Json
        $isbnCount = ($isbnData.PSObject.Properties | Measure-Object).Count
        Write-Host "   SUCCESS: Found $isbnCount ISBNs to track" -ForegroundColor Green
        
        # Show first few ISBNs
        $counter = 0
        foreach ($isbn in $isbnData.PSObject.Properties) {
            if ($counter -lt 3) {
                $title = $isbn.Value.title
                if (-not $title) { $title = "Unknown Title" }
                Write-Host "     - $($isbn.Name): $title" -ForegroundColor Gray
                $counter++
            }
        }
        if ($isbnCount -gt 3) {
            Write-Host "     ... and $($isbnCount - 3) more" -ForegroundColor Gray
        }
    } else {
        Write-Host "   WARNING: No books.json file found" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ERROR: Failed to read books.json: $_" -ForegroundColor Red
}

# Check data directory
Write-Host "`n5. Checking data directory..." -ForegroundColor Cyan
if (Test-Path "data") {
    Write-Host "   SUCCESS: Data directory exists" -ForegroundColor Green
    if (Test-Path "data\prices.csv") {
        $csvData = Import-Csv "data\prices.csv"
        Write-Host "   SUCCESS: Found $($csvData.Count) existing price records" -ForegroundColor Green
    } else {
        Write-Host "   INFO: No existing prices.csv file (will be created on first run)" -ForegroundColor Yellow
    }
} else {
    Write-Host "   INFO: Data directory will be created automatically" -ForegroundColor Yellow
}

# Check logs directory
Write-Host "`n6. Checking logs directory..." -ForegroundColor Cyan
if (Test-Path "logs") {
    Write-Host "   SUCCESS: Logs directory exists" -ForegroundColor Green
    $logFiles = Get-ChildItem "logs" -Filter "*.log"
    if ($logFiles.Count -gt 0) {
        Write-Host "   INFO: Found $($logFiles.Count) log file(s)" -ForegroundColor Yellow
        foreach ($logFile in $logFiles) {
            $size = [math]::Round($logFile.Length / 1KB, 2)
            Write-Host "     - $($logFile.Name) ($size KB)" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "   INFO: Logs directory will be created automatically" -ForegroundColor Yellow
}

# Check for existing scheduled task
Write-Host "`n7. Checking for existing scheduled task..." -ForegroundColor Cyan
try {
    $taskName = "Book Price Tracker Daily Scrape"
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName
        Write-Host "   SUCCESS: Scheduled task '$taskName' exists" -ForegroundColor Green
        Write-Host "   State: $($task.State)" -ForegroundColor Gray
        Write-Host "   Next Run: $($taskInfo.NextRunTime)" -ForegroundColor Gray
        Write-Host "   Last Result: $($taskInfo.LastTaskResult)" -ForegroundColor Gray
    } else {
        Write-Host "   INFO: No scheduled task found" -ForegroundColor Yellow
        Write-Host "   Run setup_task_scheduler.ps1 to create the task" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   INFO: Could not check scheduled tasks (may require admin privileges)" -ForegroundColor Yellow
}

Write-Host "`n" + "=" * 55 -ForegroundColor Green
Write-Host "Verification Summary:" -ForegroundColor Green

# Summary
Write-Host "`nYour scheduled scraper setup is ready! ✓" -ForegroundColor Green

Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1. Run setup_task_scheduler.ps1 to create the Windows scheduled task" -ForegroundColor White
Write-Host "2. The scraper will run automatically every day at 6:00 AM (or your chosen time)" -ForegroundColor White
Write-Host "3. Check logs\scheduled_scraper.log for execution history" -ForegroundColor White
Write-Host "4. View results at http://127.0.0.1:5000 when running the Flask app" -ForegroundColor White

Write-Host "`nManual test commands:" -ForegroundColor Cyan
Write-Host "python scheduled_scraper.py --test    # Test setup" -ForegroundColor Gray
Write-Host "python scheduled_scraper.py           # Run full scrape now" -ForegroundColor Gray
Write-Host ".\run_scheduled_scraper.bat           # Test batch file" -ForegroundColor Gray
