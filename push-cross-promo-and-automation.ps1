# push-cross-promo-and-automation.ps1
# =====================================
# Pushes ALL the new changes to GitHub in one shot.
# Run this once from PowerShell, then add NEWSAPI_KEY to GitHub Secrets.

$ErrorActionPreference = "Stop"
$root = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
Set-Location $root

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Pushing cross-promo + GitHub Actions" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Clear any stale git lock files left by a previous interrupted session
$locks = @(
  ".git\index.lock",
  ".git\HEAD.lock",
  ".git\refs\heads\master.lock"
)
foreach ($lock in $locks) {
  $full = Join-Path $root $lock
  if (Test-Path $full) {
    Remove-Item $full -Force
    Write-Host "Removed stale lock: $lock" -ForegroundColor DarkYellow
  }
}

# Reset any previously staged files so we start clean
git reset HEAD 2>$null

Write-Host "Staging files..." -ForegroundColor White

# Stage only the files we changed
git add `
  "Frontends/wallstbots.tech/assets/app.js" `
  "Frontends/wallstbots.tech/assets/style.css" `
  "Frontends/wallstbots.tech/assets/logo-wallstbots.png" `
  "Frontends/wallstbots.tech/assets/logo-bitbot13.png" `
  "Frontends/wallstbots.tech/assets/logo-lvl13.png" `
  "Frontends/wallstbots.tech/index.html" `
  "Frontends/bitbot13.tech/assets/app.js" `
  "Frontends/bitbot13.tech/assets/style.css" `
  "Frontends/bitbot13.tech/assets/logo-wallstbots.png" `
  "Frontends/bitbot13.tech/assets/logo-bitbot13.png" `
  "Frontends/bitbot13.tech/assets/logo-lvl13.png" `
  "Frontends/bitbot13.tech/index.html" `
  "Project/scripts/refresh_wallstbots.py" `
  "Project/scripts/refresh_bitbot13.py" `
  "Project/scripts/refresh_all_frontends.py" `
  "Context/BUSINESS_MODEL.md" `
  ".github/workflows/refresh-wallstbots.yml" `
  ".github/workflows/refresh-bitbot13.yml"

Write-Host "Committing..." -ForegroundColor White

$commitMsg = @"
feat: cross-promo cards + GitHub Actions auto-refresh

- Added Also from Level 13 section to wallstbots.tech and bitbot13.tech
- Added footer-network links on both sites
- GitHub Actions: wallstbots refreshes 2x/day Mon-Fri (9:35 AM + 4:05 PM ET)
- GitHub Actions: bitbot13 refreshes every 4 hours (crypto never closes)
- refresh_wallstbots.py and refresh_bitbot13.py added (full auto, no local machine needed)
- BUSINESS_MODEL.md added to Context for all future sessions
"@

git commit -m $commitMsg

Write-Host "Pushing to GitHub..." -ForegroundColor White
git push origin master

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  PUSHED. Next steps:" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "1. Cloudflare Pages will redeploy both sites in ~60 seconds" -ForegroundColor White
Write-Host ""
Write-Host "2. ADD YOUR NEWSAPI KEY TO GITHUB SECRETS (one-time setup):" -ForegroundColor Yellow
Write-Host "   Go to your GitHub repo -> Settings -> Secrets and variables -> Actions" -ForegroundColor White
Write-Host "   Click 'New repository secret'" -ForegroundColor White
Write-Host "   Name:  NEWSAPI_KEY" -ForegroundColor White
Write-Host "   Value: f45a45d7e4c94569b9f2c1b61f60a0ec" -ForegroundColor White
Write-Host ""
Write-Host "3. GitHub Actions will then run automatically:" -ForegroundColor White
Write-Host "   wallstbots.tech  - 9:35 AM ET + 4:05 PM ET (weekdays)" -ForegroundColor Gray
Write-Host "   bitbot13.tech    - Every 4 hours, 24/7" -ForegroundColor Gray
Write-Host ""

Read-Host "Press Enter to close"
