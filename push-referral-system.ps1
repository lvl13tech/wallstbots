# ============================================================================
# push-referral-system.ps1
# Commits and pushes the referral system + pricing updates to GitHub.
# Run from: C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\
# ============================================================================

Set-StrictMode -Off
$ErrorActionPreference = "Continue"

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
$wallstRoot = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
$lvl13Root  = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\1. lvl13.tech"

# --------------------------------------------------------------------------
# 1. Clear stale git lock files (both repos)
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "[1/6] Clearing stale git lock files..." -ForegroundColor Cyan

$lockFiles = @(
    "$wallstRoot\.git\index.lock",
    "$wallstRoot\.git\HEAD.lock",
    "$wallstRoot\.git\refs\heads\master.lock",
    "$lvl13Root\.git\index.lock",
    "$lvl13Root\.git\HEAD.lock",
    "$lvl13Root\.git\refs\heads\master.lock"
)
foreach ($lf in $lockFiles) {
    if (Test-Path $lf) {
        Remove-Item $lf -Force
        Write-Host "  Removed: $lf" -ForegroundColor Yellow
    }
}

# --------------------------------------------------------------------------
# 2. Stage WallStBots repo files
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/6] Staging WallStBots files..." -ForegroundColor Cyan
Set-Location $wallstRoot

git reset HEAD 2>$null

git add "Backend\referral_system_migration.sql"
git add "Backend\main.py"
git add "Frontends\wallstbots.tech\assets\app.js"
git add "Frontends\bitbot13.tech\assets\app.js"

# --------------------------------------------------------------------------
# 3. Commit WallStBots
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/6] Committing WallStBots changes..." -ForegroundColor Cyan

$commitMsgWall = @"
feat: referral system + updated pricing

- New pricing: 1st portfolio 79.99/mo or 799/yr
- Additional portfolios: 29.99/mo or 299/yr (any sister site)
- Referral codes: 50% off first month or 20% off annual for new subscribers
- Referrer earns 35 credit per redemption, auto-applied to next bill
- New DB tables: referral_redemptions, credit_transactions
- Referral code format updated to L13-XXXXXXXX
- Backend: validate-referral endpoint, account/referral dashboard endpoint
- Backend: PayPal webhook handles referral via custom field
- Frontend wallstbots: monthly/annual toggle, referral code input, /referral route
- Frontend bitbot13: same referral + pricing UI
"@

git commit -m $commitMsgWall

Write-Host ""
Write-Host "[4/6] Pushing WallStBots to GitHub..." -ForegroundColor Cyan
git push origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host "  WallStBots pushed successfully." -ForegroundColor Green
} else {
    Write-Host "  Push failed. Check git output above." -ForegroundColor Red
}

# --------------------------------------------------------------------------
# 4. Stage and commit lvl13.tech repo
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "[5/6] Staging and committing lvl13.tech changes..." -ForegroundColor Cyan
Set-Location $lvl13Root

git reset HEAD 2>$null

git add "Project\public_html\assets\app.js"

$commitMsgLvl = @"
feat: referral system + updated pricing UI

- Pricing constants: 79.99/mo, 799/yr, 29.99/mo add-on, 299/yr add-on
- Monthly/annual toggle on get-yours page
- Referral code input with live validation
- PayPal form passes referral code via custom field
- Thanks page shows referral earnings panel
- /referral route: program info + authenticated dashboard
- Dashboard shows credit balance, redemptions, transaction history
"@

git commit -m $commitMsgLvl

Write-Host ""
Write-Host "[6/6] Pushing lvl13.tech to GitHub..." -ForegroundColor Cyan
git push origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host "  lvl13.tech pushed successfully." -ForegroundColor Green
} else {
    Write-Host "  Push failed. Check git output above." -ForegroundColor Red
}

# --------------------------------------------------------------------------
# 5. Post-deploy checklist (plain Write-Host lines -- no special chars)
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "  REFERRAL SYSTEM DEPLOYED -- POST-DEPLOY CHECKLIST" -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "STEP 1 -- Run SQL migration in Supabase" -ForegroundColor Yellow
Write-Host "  1. Open https://supabase.com/dashboard and select your project"
Write-Host "  2. Go to SQL Editor"
Write-Host "  3. Open: WallStBots\Backend\referral_system_migration.sql"
Write-Host "  4. Paste and run -- safe, all changes are additive, no data loss"
Write-Host "  5. Confirm tables created: referral_redemptions, credit_transactions"
Write-Host "  6. Confirm view created: user_referral_stats"
Write-Host ""
Write-Host "STEP 2 -- Redeploy backend to Cloud Run" -ForegroundColor Yellow
Write-Host "  cd `"$wallstRoot\Backend`""
Write-Host "  gcloud run deploy wallstbots-api --source . --region us-central1"
Write-Host "  (Use your actual Cloud Run service name and region)"
Write-Host ""
Write-Host "STEP 3 -- Verify Cloudflare Pages deployments" -ForegroundColor Yellow
Write-Host "  wallstbots.tech : https://dash.cloudflare.com -> Pages -> wallstbots.tech"
Write-Host "  bitbot13.tech   : https://dash.cloudflare.com -> Pages -> bitbot13.tech"
Write-Host "  lvl13.tech      : https://dash.cloudflare.com -> Pages -> lvl13.tech"
Write-Host "  All three should auto-build from the GitHub push."
Write-Host ""
Write-Host "STEP 4 -- Test the referral flow end to end" -ForegroundColor Yellow
Write-Host "  a. Create a test subscriber, grab their L13-XXXXXXXX code"
Write-Host "  b. Open get-yours page, enter the code, confirm discount shows"
Write-Host "  c. Complete PayPal checkout, confirm webhook fires"
Write-Host "  d. Check referral_redemptions table for the new row"
Write-Host "  e. Check referrer account/referral dashboard for the 35 credit"
Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta

Set-Location $wallstRoot
