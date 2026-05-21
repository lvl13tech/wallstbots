Set-StrictMode -Off
$ErrorActionPreference = "Continue"

$root = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

Write-Host ""
Write-Host "[1/4] Clearing stale git lock files..." -ForegroundColor Cyan
$locks = @(
    "$root\.git\index.lock",
    "$root\.git\HEAD.lock",
    "$root\.git\refs\heads\master.lock"
)
foreach ($lf in $locks) {
    if (Test-Path $lf) { Remove-Item $lf -Force; Write-Host "Removed: $lf" -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "[2/4] Staging refresh script..." -ForegroundColor Cyan
Set-Location $root

git reset HEAD 2>$null
git add "Project\scripts\refresh_wallstbots.py"
Write-Host "Staged Project/scripts/refresh_wallstbots.py" -ForegroundColor Green

Write-Host ""
Write-Host "[3/4] Committing..." -ForegroundColor Cyan
git commit -m "feat: add refresh_wallstbots.py GitHub Actions engine"

Write-Host ""
Write-Host "[4/4] Pushing to GitHub..." -ForegroundColor Cyan
git push origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  REFRESH SCRIPT PUSHED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Now go to: github.com/lvl13tech/wallstbots/actions" -ForegroundColor Yellow
    Write-Host "Click Refresh wallstbots.tech -> Run workflow -> Run workflow" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "Push failed. Check git output above." -ForegroundColor Red
}

Set-Location $root
