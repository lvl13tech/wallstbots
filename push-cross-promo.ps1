# ============================================================
# Push "Also From Level XIII Tech" cross-promo section
# Run from PowerShell in the WallStBots folder:
#   .\push-cross-promo.ps1 -Token "ghp_YOUR_TOKEN_HERE"
# ============================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$Token,
    [string]$RepoPath = $PSScriptRoot
)

Write-Host ""
Write-Host "=== Cross-Promo Push ===" -ForegroundColor Cyan
Write-Host ""

Set-Location $RepoPath

# Fix corrupt git index if it exists
$indexPath = Join-Path $RepoPath ".git\index"
if (Test-Path $indexPath) {
    Remove-Item $indexPath -Force
    Write-Host "Cleared corrupt git index." -ForegroundColor Yellow
}

# Fix corrupt git config (remove trailing whitespace / null bytes)
$configPath = Join-Path $RepoPath ".git\config"
$configContent = @"
[core]
	repositoryformatversion = 0
	filemode = false
	bare = false
	logallrefupdates = true
	ignorecase = true
[user]
	email = lvl13cs@gmail.com
	name = M13
[remote "origin"]
	url = https://github.com/lvl13tech/wallstbots.git
	fetch = +refs/heads/*:refs/remotes/origin/*
[branch "master"]
	remote = origin
	merge = refs/heads/master
"@
Set-Content -Path $configPath -Value $configContent -Encoding UTF8
Write-Host "Fixed git config." -ForegroundColor Yellow

# Set remote with token
git remote set-url origin "https://${Token}@github.com/lvl13tech/wallstbots.git"

# Stage only the two changed app.js files
git add Frontends/wallstbots.tech/assets/app.js
git add Frontends/bitbot13.tech/assets/app.js

# Commit
git commit -m "Add 'Also From Level XIII Tech' cross-promo section to home pages

- wallstbots.tech: links to lvl13.tech and bitbot13.tech
- bitbot13.tech: links to lvl13.tech and wallstbots.tech
- Section renders below the performance chart on the home page"

# Push
Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
git push origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "SUCCESS! Cross-promo section live." -ForegroundColor Green
    Write-Host "Cloudflare will auto-deploy both sites in ~2 minutes." -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "Push failed. Check your token." -ForegroundColor Red
}

# Remove token from remote URL for security
git remote set-url origin "https://github.com/lvl13tech/wallstbots.git"
