# PowerShell script to set up Windows Task Scheduler for Book Price Tracker
# Run this script as Administrator to create the scheduled task

param(
    [string]$Time = "06:00",  # Default time is 6:00 AM
    [string]$ProjectPath = "t:\Coding_Projects\BooksFindr\books_findr"
)

Write-Host "Setting up Windows Task Scheduler for Book Price Tracker..." -ForegroundColor Green
Write-Host "Time: $Time" -ForegroundColor Yellow
Write-Host "Project Path: $ProjectPath" -ForegroundColor Yellow

# Verify the batch file exists
$batchFile = Join-Path $ProjectPath "run_scheduled_scraper.bat"
if (-not (Test-Path $batchFile)) {
    Write-Error "Batch file not found: $batchFile"
    Write-Host "Please ensure the batch file exists before running this script."
    exit 1
}

# Verify virtual environment exists
$venvPath = Join-Path $ProjectPath "venv\Scripts\activate.bat"
if (-not (Test-Path $venvPath)) {
    Write-Error "Virtual environment not found: $venvPath"
    Write-Host "Please ensure the virtual environment is set up correctly."
    exit 1
}

# Test the scheduled scraper first
Write-Host "`nTesting scheduled scraper..." -ForegroundColor Cyan
try {
    Set-Location $ProjectPath
    $testResult = & .\run_scheduled_scraper.bat
    if ($LASTEXITCODE -eq 0) {
        Write-Host "SUCCESS: Scheduled scraper test passed!" -ForegroundColor Green
    } else {
        Write-Error "Scheduled scraper test failed!"
        exit 1
    }
} catch {
    Write-Error "Error testing scheduled scraper: $_"
    exit 1
}

# Create the scheduled task
Write-Host "`nCreating scheduled task..." -ForegroundColor Cyan

try {
    # Define task parameters
    $taskName = "Book Price Tracker Daily Scrape"
    $description = "Daily scraping of book prices for BooksFindr application"
    
    # Create action
    $action = New-ScheduledTaskAction -Execute $batchFile -WorkingDirectory $ProjectPath
    
    # Create trigger (daily at specified time)
    $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    
    # Create settings
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable
    
    # Create principal (run as current user)
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U
    
    # Register the task
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description $description -Force
    
    Write-Host "SUCCESS: Scheduled task '$taskName' created successfully!" -ForegroundColor Green
    Write-Host "The task will run daily at $Time" -ForegroundColor Yellow
    
} catch {
    Write-Error "Failed to create scheduled task: $_"
    exit 1
}

# Show task information
Write-Host "`nTask Information:" -ForegroundColor Cyan
try {
    $task = Get-ScheduledTask -TaskName $taskName
    Write-Host "Task Name: $($task.TaskName)" -ForegroundColor White
    Write-Host "State: $($task.State)" -ForegroundColor White
    Write-Host "Next Run: $((Get-ScheduledTask -TaskName $taskName | Get-ScheduledTaskInfo).NextRunTime)" -ForegroundColor White
} catch {
    Write-Warning "Could not retrieve task information: $_"
}

Write-Host "`nSetup complete! Your book price tracker will now run automatically every day at $Time" -ForegroundColor Green

Write-Host "`nUseful commands:" -ForegroundColor Cyan
Write-Host "  View task:       Get-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host "  Run task now:    Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host "  Disable task:    Disable-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host "  Enable task:     Enable-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host "  Remove task:     Unregister-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray

Write-Host "`nCheck logs at: $ProjectPath\logs\scheduled_scraper.log" -ForegroundColor Yellow
