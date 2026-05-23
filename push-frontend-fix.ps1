# ============================================================================
# push-frontend-fix.ps1
# Pushes wallstbots.tech + bitbot13.tech frontend fixes to GitHub.
# Includes logo images + corrected "Also from Level 13" card section.
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
Write-Host "[2/4] Staging frontend files..." -ForegroundColor Cyan
Set-Location $root

git reset HEAD 2>$null

# wallstbots.tech
git add "Frontends/wallstbots.tech/index.html"
git add "Frontends/wallstbots.tech/assets/app.js"
git add "Frontends/wallstbots.tech/assets/style.css"
git add "Frontends/wallstbots.tech/assets/logo-lvl13.png"
git add "Frontends/wallstbots.tech/assets/logo-bitbot13.png"
git add "Frontends/wallstbots.tech/assets/logo-wallstbots.png"

# bitbot13.tech
git add "Frontends/bitbot13.tech/index.html"
git add "Frontends/bitbot13.tech/assets/app.js"
git add "Frontends/bitbot13.tech/assets/style.css"
git add "Frontends/bitbot13.tech/assets/logo-lvl13.png"
git add "Frontends/bitbot13.tech/assets/logo-bitbot13.png"
git add "Frontends/bitbot13.tech/assets/logo-wallstbots.png"

Write-Host "  Staged wallstbots.tech + bitbot13.tech" -ForegroundColor Green

# 3. Commit
Write-Host ""
Write-Host "[3/4] Committing..." -ForegroundColor Cyan

git commit -m "fix: wallstbots + bitbot13 Also From section now matches lvl13 (grid layout + logos)"

# 4. Push
Write-Host ""
Write-Host "[4/4] Pushing to GitHub..." -ForegroundColor Cyan
git push origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  PUSHED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Cloudflare Pages will auto-deploy both sites." -ForegroundColor Yellow
    Write-Host "Wait ~60 seconds then hard-refresh your browser." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Both sites will now show:" -ForegroundColor White
    Write-Host "  - Side-by-side cards with logo images" -ForegroundColor White
    Write-Host "  - Proper Visit [site] buttons" -ForegroundColor White
    Write-Host "  - Matching layout to lvl13.tech" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "  Push failed. Check git output above." -ForegroundColor Red
}

Set-Location $root
