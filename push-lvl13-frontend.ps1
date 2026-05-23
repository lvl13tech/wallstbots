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

# ── Stage the files ─────────────────────────────────────────────
git add Frontends/lvl13.tech/index.html
git add Frontends/lvl13.tech/assets/app.js
git add Frontends/lvl13.tech/assets/style.css
git add Frontends/lvl13.tech/assets/favicon.svg
git add Frontends/lvl13.tech/assets/logo.svg
git add Frontends/lvl13.tech/assets/robot.svg
git add Frontends/lvl13.tech/assets/og-image.svg
git add Project/public_html/assets/app.js

git status

# ── Commit & push ────────────────────────────────────────────────
git commit -m "fix: restore lvl13.tech SPA + add Also From cross-promo to all 3 sites"
git push origin master

Write-Host ""
Write-Host "Done. Cloudflare Pages will rebuild lvl13.tech in ~60 seconds." -ForegroundColor Green
Write-Host "Upload Project/public_html/assets/app.js to HostGator to update the live site." -ForegroundColor Yellow
