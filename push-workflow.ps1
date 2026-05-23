# ============================================================================
# push-workflow.ps1
# Pushes the GitHub Actions workflow + refresh script to GitHub.
# This is what enables the bots to run automatically every trading day.
# Run from: C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\
# ============================================================================

Set-StrictMode -Off
$ErrorActionPreference = "Continue"

$root = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

# 1. Clear stale lock files
Write-Host ""
Write-Host "[1/4] Clearing stale git lock files..." -ForegroundColor Cyan
$locks = @(
    "$root\.git\index.lock",
    "$root\.git\HEAD.lock",
    "$root\.git\refs\heads\master.lock"
)
foreach ($lf in $locks) {
    if (Test-Path $lf) { Remove-Item $lf -Force; Write-Host "  Removed: $lf" -ForegroundColor Yellow }
}

# 2. Stage files
Write-Host ""
Write-Host "[2/4] Staging workflow + refresh script..." -ForegroundColor Cyan
Set-Location $root

git reset HEAD 2>$null

git add ".github\workflows\refresh-wallstbots.yml"
git add "Project\scripts\refresh_wallstbots.py"

Write-Host "  Staged .github/workflows/refresh-wallstbots.yml" -ForegroundColor Green
Write-Host "  Staged Project/scripts/refresh_wallstbots.py" -ForegroundColor Green

# 3. Commit
Write-Host ""
Write-Host "[3/4] Committing..." -ForegroundColor Cyan

git commit -m "feat: add GitHub Actions auto-refresh workflow (9:35 AM, 12:05 PM, 4:05 PM ET)"

# 4. Push
Write-Host ""
Write-Host "[4/4] Pushing to GitHub..." -ForegroundColor Cyan
git push origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  WORKFLOW PUSHED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Go to: github.com/lvl13tech/wallstbots/actions"
    Write-Host "  2. Click 'Refresh wallstbots.tech' in the left sidebar"
    Write-Host "  3. Click 'Run workflow' -> 'Run workflow' to test immediately"
    Write-Host ""
    Write-Host "The workflow will also run automatically:" -ForegroundColor Yellow
    Write-Host "  - 9:35 AM ET (market open)"
    Write-Host "  - 12:05 PM ET (midday)"
    Write-Host "  - 4:05 PM ET (close)"
    Write-Host "  on every weekday from now on."
    Write-Host ""
} else {
    Write-Host "  Push failed. Check git output above." -ForegroundColor Red
}

Set-Location $root
