# push-jwt-fix.ps1
# One-click: clear git locks, push the ES256 JWT fix + admin.html fix to GitHub
# Run from PowerShell: Right-click → Run with PowerShell

$ErrorActionPreference = "Stop"
$repoPath = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

Write-Host "=== WallStBots: Push JWT Fix ===" -ForegroundColor Cyan
Set-Location $repoPath

# Remove stale lock files
$locks = @(
    ".git\index.lock",
    ".git\refs\heads\master.lock",
    ".git\objects\maintenance.lock",
    ".git\HEAD.lock"
)
foreach ($lock in $locks) {
    if (Test-Path $lock) {
        Remove-Item $lock -Force
        Write-Host "Removed $lock" -ForegroundColor Yellow
    }
}

# Show current status
Write-Host "`nCurrent git log (top 3):" -ForegroundColor Cyan
git log --oneline -3

# Push to GitHub
Write-Host "`nPushing to GitHub..." -ForegroundColor Cyan
git push origin master

Write-Host "`n=== Push complete! ===" -ForegroundColor Green
Write-Host "Now deploy to Cloud Run from Google Cloud Shell:" -ForegroundColor Yellow
Write-Host "  cd ~/wallstbots/Backend && git pull origin master && gcloud run deploy wallstbots-backend --source . --region us-east1 --allow-unauthenticated --quiet --project lvl13-tracker-496402" -ForegroundColor White
