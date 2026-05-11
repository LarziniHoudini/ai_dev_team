# Get the location of the script to ensure paths are correct
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $PSScriptRoot

Write-Host "--- Initializing Java Agent Environment ---" -ForegroundColor Cyan

# 1. Check and Start Ollama if missing
$ollamaProcess = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollamaProcess) {
    Write-Host "Ollama is not running. Launching it now..." -ForegroundColor Yellow
    # Start Ollama minimized or in the background
    Start-Process "ollama app.exe" 
    
    # Give it a few seconds to initialize the server
    Start-Sleep -Seconds 3
    Write-Host "Ollama should be active in the system tray." -ForegroundColor Green
} else {
    Write-Host "Ollama is already running." -ForegroundColor Green
}

# 2. Check and Activate Python Virtual Environment
if (Test-Path ".\venv\Scripts\activate.ps1") {
    Write-Host "Activating Virtual Environment..." -ForegroundColor Yellow
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "ERROR: Virtual environment not found. Please run your setup script first." -ForegroundColor Red
    Pause
    exit
}

# 3. Launch the Flask App
Write-Host "Launching Web Server at http://127.0.0.1:5000" -ForegroundColor Green
# Using 'python' directly as the venv is now active
python .\web_ui\app.py