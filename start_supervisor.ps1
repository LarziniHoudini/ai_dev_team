# start_supervisor.ps1

# 1. Clear the screen for a fresh start
Clear-Host
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   JAVA AGENTIC TEAM: SUPERVISOR STARTING    " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# 2. Set the working directory to the project root
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $PSScriptRoot

# 3. Activate the virtual environment
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "[*] Activating Virtual Environment..." -ForegroundColor Yellow
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "[!] Error: Virtual environment (venv) not found!" -ForegroundColor Red
    Pause
    exit
}

# 4. Check if the agents folder exists
if (Test-Path ".\agents\supervisor.py") {
    Write-Host "[*] Launching Supervisor Agent..." -ForegroundColor Green
    Write-Host "[i] Tip: Use the Web UI to select a repo first." -ForegroundColor Gray
    Write-Host "---------------------------------------------"
    
    # Run the python script
    python .\agents\supervisor.py
} else {
    Write-Host "[!] Error: supervisor.py not found in the 'agents' folder!" -ForegroundColor Red
    Pause
}

# 5. Keep the window open if it crashes
Write-Host "`n---------------------------------------------"
Write-Host "Supervisor has stopped." -ForegroundColor Yellow
Pause