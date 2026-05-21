# run_refresh.ps1
# ================
# Double-click this (or run in PowerShell) to refresh wallstbots.tech and
# bitbot13.tech with live prices, signals, and news — then push to GitHub.
#
# Requirements (one-time setup):
#   pip install yfinance requests

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  WallStBots + BitBot13 Frontend Refresh" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    python --version | Out-Null
} catch {
    Write-Host "ERROR: Python not found. Install Python 3.10+ and add to PATH." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check yfinance
$yf = python -c "import yfinance" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing yfinance + requests..." -ForegroundColor Yellow
    pip install yfinance requests
}

Write-Host "Running refresh scripts..." -ForegroundColor Green
Write-Host ""

Set-Location $root
python "Project\scripts\refresh_all_frontends.py"

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  DONE — check wallstbots.tech + bitbot13.tech" -ForegroundColor Green
Write-Host "  (Cloudflare Pages deploys in ~60 seconds)"     -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""

Read-Host "Press Enter to close"
