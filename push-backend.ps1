param(
    [Parameter(Mandatory=$true)]
    [string]$Token
)

$RepoRoot = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
Set-Location $RepoRoot

# ── Clean up any git lock or corrupt index ──────────────────────
if (Test-Path ".git\index.lock") { Remove-Item ".git\index.lock" -Force }
if (Test-Path ".git\index")      { Remove-Item ".git\index"      -Force }

# ── Rewrite clean git config ────────────────────────────────────
$cfg = @"
[core]
	repositoryformatversion = 0
	filemode = false
	bare = false
	logallrefupdates = true
	symlinks = false
	ignorecase = true
[remote "origin"]
	url = https://$Token@github.com/lvl13tech/wallstbots.git
	fetch = +refs/heads/*:refs/remotes/origin/*
[branch "master"]
	remote = origin
	merge = refs/heads/master
"@
[System.IO.File]::WriteAllText("$RepoRoot\.git\config", $cfg)

# ── Stage backend + frontend + GCP script ───────────────────────
git add Backend/main.py
git add Backend/Dockerfile
git add Backend/requirements.txt
git add Backend/user_tracker_migration.sql
git add Backend/onboarding_migration.sql
git add Project/scripts/refresh_data.py
git add Frontends/lvl13.tech/assets/app.js
git add Project/public_html/assets/app.js
git add Frontends/wallstbots.tech/assets/app.js
git add Frontends/bitbot13.tech/assets/app.js

git status

# ── Commit & push ────────────────────────────────────────────────
git commit -m "feat: per-user tracker - PayPal webhook, setup flow, nightly bot loop, private dashboard"
git push origin master

Write-Host ""
Write-Host "Done. GitHub is updated." -ForegroundColor Green
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "  1. Run the DB migration in Supabase (SQL editor):"
Write-Host "       Backend/user_tracker_migration.sql"
Write-Host "  2. Rebuild + redeploy the Cloud Run backend:"
Write-Host "       See DEPLOY_BACKEND.md for the full gcloud commands"
Write-Host "  3. Upload Project/public_html/assets/app.js to HostGator via FTP"
Write-Host "       Path: public_html/assets/app.js"
Write-Host "  4. Set Cloud Run env vars (if not already set):"
Write-Host "       SENDGRID_API_KEY, FROM_EMAIL, PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET"
Write-Host "       PAYPAL_PLAN_WALLSTBOTS, PAYPAL_PLAN_BITBOT13"
