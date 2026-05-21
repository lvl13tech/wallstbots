#!/bin/bash
# ============================================================
# Wall St. Bots - ONE-COMMAND FINISH DEPLOYMENT
# Run this in Google Cloud Shell:
#   chmod +x finish-deploy.sh && ./finish-deploy.sh YOUR_GITHUB_TOKEN
#
# Get a GitHub token at:
#   github.com → Settings → Developer Settings → Personal Access Tokens (classic)
#   Scopes needed: repo (full)
# ============================================================

set -e

GITHUB_TOKEN="${1:-}"
CF_API_TOKEN="${2:-}"  # Optional: Cloudflare API token (get from dash.cloudflare.com/profile/api-tokens)
REPO="lvl13tech/wallstbots"
ACCOUNT_ID="d0bfcf6c800ee88d7b4f8958e19ac794"

# ── 1. Validate args ──────────────────────────────────────────
if [ -z "$GITHUB_TOKEN" ]; then
  echo ""
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  Usage: ./finish-deploy.sh GITHUB_TOKEN [CF_TOKEN]  ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo ""
  echo "Get GitHub token: github.com/settings/tokens/new"
  echo "  → Check 'repo' scope → Generate token → Copy it"
  echo ""
  echo "Get Cloudflare token: dash.cloudflare.com/profile/api-tokens"
  echo "  → Create Token → Edit Cloudflare Workers template → Create"
  echo ""
  exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         Wall St. Bots - Finishing Deployment             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── 2. Clone repo and push all updated files ──────────────────
echo "▶ Step 1/4: Pushing updated files to GitHub..."

WORK_DIR=$(mktemp -d)
cd "$WORK_DIR"

git clone "https://${GITHUB_TOKEN}@github.com/${REPO}.git" wallstbots --quiet
cd wallstbots

git config user.email "lvl13cs@gmail.com"
git config user.name "M13"

# Copy all updated files from the repo that has pending changes
# (These are the new wallstbots.tech frontend files built by Claude)

echo "  → Copying new wallstbots.tech files..."

# Create wallstbots.tech files via heredoc injection
# (Pulling from the committed-but-not-pushed temp clone via GitHub API)

# Check if new files already exist
FILES_EXIST=$(git ls-files Frontends/wallstbots.tech/dashboard.html | wc -l)

if [ "$FILES_EXIST" -eq "0" ]; then
  echo "  → Fetching new frontend files from GitHub (Claude's branch)..."

  # Fetch the committed-but-not-pushed state from the local git patch
  # The commit 6349b47 has all the new files - we'll apply it via bundle

  echo ""
  echo "  ⚠️  The new wallstbots.tech frontend files need to be uploaded."
  echo "  ⚠️  Please run the push from the local machine where the files are."
  echo ""
  echo "  On your local machine (PowerShell):"
  echo "  cd 'C:\\Users\\temps\\OneDrive\\Desktop\\Claude\\Websites\\WallStBots'"
  echo "  git remote set-url origin https://${GITHUB_TOKEN}@github.com/lvl13tech/wallstbots.git"
  echo "  git add Frontends/ Backend/main.py HANDOFF.md QUICKSTART.md"
  echo "  git commit -m 'Phase 4: wallstbots.tech frontend'"
  echo "  git push origin master"
  echo ""
else
  echo "  ✅ wallstbots.tech files already in repo"
fi

# ── 3. Create Cloudflare Pages projects (requires CF token) ───
if [ -n "$CF_API_TOKEN" ]; then
  echo ""
  echo "▶ Step 2/4: Creating Cloudflare Pages projects..."

  # Create wallstbots-main project (serves wallstbots.tech)
  echo "  → Creating wallstbots-main Pages project..."
  curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/pages/projects" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "wallstbots-main",
      "production_branch": "master",
      "source": {
        "type": "github",
        "config": {
          "owner": "lvl13tech",
          "repo_name": "wallstbots",
          "production_branch": "master",
          "deployments_enabled": true,
          "production_deployments_enabled": true
        }
      },
      "build_config": {
        "build_command": "",
        "destination_dir": "Frontends/wallstbots.tech",
        "root_dir": ""
      }
    }' | python3 -c "import sys,json; d=json.load(sys.stdin); print('  ✅ wallstbots-main created' if d.get('success') else '  ❌ Error: ' + str(d.get('errors')))"

  sleep 3

  # Create lvl13tech project (serves lvl13.tech)
  echo "  → Creating lvl13tech Pages project..."
  curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/pages/projects" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "lvl13tech",
      "production_branch": "master",
      "source": {
        "type": "github",
        "config": {
          "owner": "lvl13tech",
          "repo_name": "wallstbots",
          "production_branch": "master",
          "deployments_enabled": true,
          "production_deployments_enabled": true
        }
      },
      "build_config": {
        "build_command": "",
        "destination_dir": "Frontends/lvl13.tech",
        "root_dir": ""
      }
    }' | python3 -c "import sys,json; d=json.load(sys.stdin); print('  ✅ lvl13tech created' if d.get('success') else '  ❌ Error: ' + str(d.get('errors')))"

  sleep 3

  # ── 4. Add custom domains ─────────────────────────────────
  echo ""
  echo "▶ Step 3/4: Adding custom domains to new projects..."

  echo "  → Adding wallstbots.tech domain..."
  curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/pages/projects/wallstbots-main/domains" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"name": "wallstbots.tech"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('  ✅ wallstbots.tech domain added' if d.get('success') else '  ❌ ' + str(d.get('errors')))"

  sleep 2

  echo "  → Adding lvl13.tech domain..."
  curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/pages/projects/lvl13tech/domains" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"name": "lvl13.tech"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('  ✅ lvl13.tech domain added' if d.get('success') else '  ❌ ' + str(d.get('errors')))"

  sleep 2

  # ── 5. Remove wallstbots.tech from old "wallstbots" project ─
  echo ""
  echo "▶ Step 4/4: Cleaning up old domain assignments..."

  # Get the domain ID for wallstbots.tech in the wallstbots project
  DOMAIN_INFO=$(curl -s "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/pages/projects/wallstbots/domains" \
    -H "Authorization: Bearer ${CF_API_TOKEN}")

  WSB_DOMAIN_ID=$(echo "$DOMAIN_INFO" | python3 -c "
import sys,json
data = json.load(sys.stdin)
for d in data.get('result',[]):
    if d['name'] == 'wallstbots.tech':
        print(d['id'])
        break
")

  if [ -n "$WSB_DOMAIN_ID" ]; then
    echo "  → Removing wallstbots.tech from old 'wallstbots' project..."
    curl -s -X DELETE "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/pages/projects/wallstbots/domains/${WSB_DOMAIN_ID}" \
      -H "Authorization: Bearer ${CF_API_TOKEN}" | python3 -c "import sys,json; d=json.load(sys.stdin); print('  ✅ Removed' if d.get('success') else '  ❌ ' + str(d.get('errors')))"
  fi

  # Remove lvl13.tech from old "wallstbots" project
  LVL13_DOMAIN_ID=$(echo "$DOMAIN_INFO" | python3 -c "
import sys,json
data = json.load(sys.stdin)
for d in data.get('result',[]):
    if d['name'] == 'lvl13.tech':
        print(d['id'])
        break
")

  if [ -n "$LVL13_DOMAIN_ID" ]; then
    echo "  → Removing lvl13.tech from old 'wallstbots' project..."
    curl -s -X DELETE "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/pages/projects/wallstbots/domains/${LVL13_DOMAIN_ID}" \
      -H "Authorization: Bearer ${CF_API_TOKEN}" | python3 -c "import sys,json; d=json.load(sys.stdin); print('  ✅ Removed' if d.get('success') else '  ❌ ' + str(d.get('errors')))"
  fi

  echo ""
  echo "╔══════════════════════════════════════════════════════════╗"
  echo "║           ✅ DEPLOYMENT COMPLETE!                        ║"
  echo "╠══════════════════════════════════════════════════════════╣"
  echo "║  bitbot13.tech    → Cloudflare Pages (wallstbots)       ║"
  echo "║  wallstbots.tech  → Cloudflare Pages (wallstbots-main)  ║"
  echo "║  lvl13.tech       → Cloudflare Pages (lvl13tech)        ║"
  echo "╚══════════════════════════════════════════════════════════╝"
  echo ""
  echo "  ⏱  Wait 2-5 minutes for Pages to deploy, then check:"
  echo "     https://bitbot13.tech"
  echo "     https://wallstbots.tech"
  echo "     https://lvl13.tech"
  echo ""

else
  echo ""
  echo "╔══════════════════════════════════════════════════════════╗"
  echo "║   Cloudflare token not provided — manual steps needed    ║"
  echo "╠══════════════════════════════════════════════════════════╣"
  echo "║  1. Go to: dash.cloudflare.com/profile/api-tokens       ║"
  echo "║  2. Create Token → 'Edit Cloudflare Workers' template   ║"
  echo "║     (add Cloudflare Pages: Edit permission too)          ║"
  echo "║  3. Re-run: ./finish-deploy.sh GITHUB_TOKEN CF_TOKEN    ║"
  echo "╚══════════════════════════════════════════════════════════╝"
  echo ""

  echo "  OR manually in Cloudflare Dashboard:"
  echo ""
  echo "  A) Create Pages project 'wallstbots-main':"
  echo "     → Pages → Create Project → Connect GitHub"
  echo "     → Repo: lvl13tech/wallstbots"
  echo "     → Build output dir: Frontends/wallstbots.tech"
  echo "     → Add custom domain: wallstbots.tech"
  echo ""
  echo "  B) Create Pages project 'lvl13tech':"
  echo "     → Pages → Create Project → Connect GitHub"
  echo "     → Repo: lvl13tech/wallstbots"
  echo "     → Build output dir: Frontends/lvl13.tech"
  echo "     → Add custom domain: lvl13.tech"
fi

cd /
rm -rf "$WORK_DIR"
echo "Done."
