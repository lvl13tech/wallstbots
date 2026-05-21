# ============================================================
# Wall St. Bots - Push all pending changes to GitHub
# Run from PowerShell in the WallStBots folder:
#   .\push-to-github.ps1 -Token "ghp_YOUR_TOKEN_HERE"
#
# Get token at: github.com/settings/tokens/new
#   Scopes: repo (full)
# ============================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$Token,

    [string]$RepoPath = $PSScriptRoot
)

Write-Host ""
Write-Host "=== Wall St. Bots GitHub Push ===" -ForegroundColor Cyan
Write-Host ""

Set-Location $RepoPath

# Configure git identity
git config user.email "lvl13cs@gmail.com"
git config user.name "M13"

# Set remote with token
git remote set-url origin "https://${Token}@github.com/lvl13tech/wallstbots.git"

# Stage all frontend and backend changes
git add Frontends/wallstbots.tech/
git add Frontends/bitbot13.tech/
git add Frontends/lvl13.tech/
git add Backend/main.py
git add Backend/onboarding_migration.sql
git add HANDOFF.md
git add QUICKSTART.md
git add TECHNICAL_REFERENCE.md
git add Project/scripts/refresh_news.py
git add deploy-tracker-update.ps1

# Commit
git commit -m "Phase 4: wallstbots.tech full frontend + backend updates

- wallstbots.tech: dashboard, bot-detail, login, auth.js, api.js
- Updated all 3 frontends to latest Cloud Run API URL
- Backend: onboarding migration, stock picks endpoints
- Added project documentation files" 2>&1

# Push
Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
git push origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "SUCCESS! Files pushed to GitHub." -ForegroundColor Green
    Write-Host ""
    Write-Host "Cloudflare Pages will auto-deploy bitbot13.tech in ~2 minutes." -ForegroundColor Green
    Write-Host ""
    Write-Host "NEXT: Run finish-deploy.sh in Cloud Shell to create the" -ForegroundColor Yellow
    Write-Host "      wallstbots.tech and lvl13.tech Pages projects." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Or manually in Cloudflare Dashboard (dash.cloudflare.com):" -ForegroundColor White
    Write-Host "  1. Pages > Create Project > Connect GitHub > lvl13tech/wallstbots" -ForegroundColor White
    Write-Host "     Build dir: Frontends/wallstbots.tech  |  Domain: wallstbots.tech" -ForegroundColor White
    Write-Host "  2. Pages > Create Project > Connect GitHub > lvl13tech/wallstbots" -ForegroundColor White
    Write-Host "     Build dir: Frontends/lvl13.tech  |  Domain: lvl13.tech" -ForegroundColor White
} else {
    Write-Host "Push failed. Check your GitHub token." -ForegroundColor Red
}

# Remove token from remote URL for security
git remote set-url origin "https://github.com/lvl13tech/wallstbots.git"
