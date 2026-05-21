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
Write-Host "[2/4] Staging data files..." -ForegroundColor Cyan
Set-Location $root

git reset HEAD 2>$null
git add "Frontends\wallstbots.tech\data\state.json"
git add "Frontends\wallstbots.tech\data\signals.json"
git add "Frontends\wallstbots.tech\data\news.json"
git add "Frontends\wallstbots.tech\data\reports.json"
Write-Host "Staged all data files" -ForegroundColor Green

Write-Host ""
Write-Host "[3/4] Committing..." -ForegroundColor Cyan
git commit -m "feat: add wallstbots.tech initial data files (state, signals, news, reports)"

Write-Host ""
Write-Host "[4/4] Pushing to GitHub..." -ForegroundColor Cyan
git push origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  DATA FILES PUSHED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Now re-run the workflow:" -ForegroundColor Yellow
    Write-Host "  github.com/lvl13tech/wallstbots/actions" -ForegroundColor Yellow
    Write-Host "  Refresh wallstbots.tech -> Run workflow -> Run workflow" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "Push failed. Check git output above." -ForegroundColor Red
}

Set-Location $root
