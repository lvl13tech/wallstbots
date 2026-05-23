# ============================================================================
# push-strategy-update.ps1
# Commits and pushes the enhanced bot strategy logic to GitHub.
# Run from: C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\
# ============================================================================

Set-StrictMode -Off
$ErrorActionPreference = "Continue"

$wallstRoot = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

# --------------------------------------------------------------------------
# 1. Clear stale git lock files
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "[1/4] Clearing stale git lock files..." -ForegroundColor Cyan

$lockFiles = @(
    "$wallstRoot\.git\index.lock",
    "$wallstRoot\.git\HEAD.lock",
    "$wallstRoot\.git\refs\heads\master.lock"
)
foreach ($lf in $lockFiles) {
    if (Test-Path $lf) {
        Remove-Item $lf -Force
        Write-Host "  Removed: $lf" -ForegroundColor Yellow
    }
}

# --------------------------------------------------------------------------
# 2. Stage files
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/4] Staging strategy files..." -ForegroundColor Cyan
Set-Location $wallstRoot

git reset HEAD 2>$null

git add "Project\scripts\refresh_wallstbots.py"
git add ".github\workflows\refresh-wallstbots.yml"

# --------------------------------------------------------------------------
# 3. Commit
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/4] Committing strategy update..." -ForegroundColor Cyan

$commitMsg = @"
feat: enhanced bot strategies (BOT13 precision intraday, ORACLE + WIZARD composite scoring)

BOT13 -- Precision Intraday Momentum:
- Minimum 1.0% move entry gate (was 0.3%)
- Market breadth gate: >33% down >2% -> cash
- Overextension penalty: >8% moves get 0.55x weight (reversal risk)
- Signal-strength weighted allocation, clamped 12-33%
- Embedded stop-loss -1.5%, profit target +3.0% per position
- Session phase detection: morning / midday / close (ET)
- Cumulative session log per day, resets each morning
- Requires 3+ qualified candidates or goes CASH

ORACLE -- Adaptive Weekly Momentum (recomputes every Monday):
- 90-day OHLCV history via yf.download()
- Composite score: ret5*40% + ret20*30% + RSI quality*20% + volume*10%
- RSI >75 scored negatively (overbought penalty)
- Quality gate: 20d return must be positive
- Sector cap: max 2 picks per sector
- Score-weighted allocation, clamped 12-35%

WIZARD -- Quality Monthly Momentum (recomputes 1st trading day each month):
- Score: ret20*35% + ret60*35% + Sharpe proxy*20% + MA50 distance*10%
- Quality gate: 60d return must be positive
- Quartile sizing: top 25% -> 3x weight, middle -> 1.8x, bottom -> 1.0x
- Sector cap: max 3 picks per sector
- Intra-month: positions down >12% flagged stop_triggered

GitHub Actions: added 12:05 PM ET (16:05 UTC) midday run for BOT13
"@

git commit -m $commitMsg

# --------------------------------------------------------------------------
# 4. Push
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/4] Pushing to GitHub..." -ForegroundColor Cyan
git push origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  STRATEGY UPDATE PUSHED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "What happens next:" -ForegroundColor Yellow
    Write-Host "  1. Cloudflare Pages will auto-build the frontend (no action needed)"
    Write-Host "  2. GitHub Actions will run at next scheduled trigger:"
    Write-Host "     - 9:35 AM ET  (market open -- BOT13 morning session)"
    Write-Host "     - 12:05 PM ET (midday -- BOT13 midday session)"
    Write-Host "     - 4:05 PM ET  (close -- BOT13 close session)"
    Write-Host "  3. ORACLE recomputes automatically every Monday morning run"
    Write-Host "  4. WIZARD recomputes automatically on the 1st trading day each month"
    Write-Host ""
    Write-Host "To test immediately:" -ForegroundColor Yellow
    Write-Host "  Go to GitHub -> Actions -> Refresh wallstbots.tech -> Run workflow"
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "  Push failed. Check git output above." -ForegroundColor Red
}

Set-Location $wallstRoot
