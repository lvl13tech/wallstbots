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
Write-Host "[2/4] Staging fixed workflow..." -ForegroundColor Cyan
Set-Location $root

git reset HEAD 2>$null
git add ".github\workflows\refresh-wallstbots.yml"
Write-Host "Staged .github/workflows/refresh-wallstbots.yml" -ForegroundColor Green

Write-Host ""
Write-Host "[3/4] Committing..." -ForegroundColor Cyan
git commit -m "fix: use python -m pip with --break-system-packages for Ubuntu runner"

Write-Host ""
Write-Host "[4/4] Pushing to GitHub..." -ForegroundColor Cyan
git push origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  WORKFLOW FIX PUSHED" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Now go trigger the workflow again:" -ForegroundColor Yellow
    Write-Host "  github.com/lvl13tech/wallstbots/actions" -ForegroundColor Yellow
    Write-Host "  Refresh wallstbots.tech -> Run workflow -> Run workflow" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "Push failed. Check git output above." -ForegroundColor Red
}

Set-Location $root
