# Level 13 — Handoff Doc (2026-05-21)

Status snapshot of the three sites and what's still pending.

---

## Live state right now

| Site | Hosting | Code status | Data status | Notes |
|------|---------|-------------|-------------|-------|
| **bitbot13.tech** | Cloudflare Pages (auto-deploys from GitHub `master`) | ✓ latest pushed | ✓ refreshed with canonical signal shape | Fully working — header logo, footer cross-promo, signals, crypto-only news |
| **wallstbots.tech** | Cloudflare Pages (auto-deploys from GitHub `master`) | ⚠ latest pushed but footer "BitBot13"→"bitbot13.tech" rename is in the latest unpushed commit | ✓ refreshed with canonical signal shape | Footer link text mismatch will resolve after next push |
| **lvl13.tech** | HostGator (manual FTP upload — `sh00167.hostgator.com`, FTP user `178212781`, creds saved in `Project/config/secrets.json`) | ⚠ latest local code NOT uploaded yet | ✗ no data refresh script for lvl13 (only manual data, no cron) | Needs file uploads — see "Pending lvl13 upload" below |

---

## What changed this session (all already in your local files)

### Frontend
- **All 3 login.html pages unified to bitbot13's design** (dark theme, cyan accent, tabs, big rounded button). Each site shows its own brand name.
- **lvl13/index.html**: header uses `assets/logo.svg`; footer cross-link reads `bitbot13.tech` (lowercase, matching style); footer brand shows favicon + "Level XIII Tech".
- **lvl13/assets/app.js**: added cross-promo PNG cards section "Also from Level 13" with Wall St. Bots + BitBot13 cards; removed the older redundant "Also From Level XIII Tech" simple-cards section (only one cross-promo block on the page now); fixed `/login` and `/signup` hash routes; restored truncated tail.
- **lvl13/assets/logo.svg + favicon.svg**: replaced truncated versions with the working bitbot13-style robot icon.
- **bitbot13/assets/app.js**: fixed broken chatbot input handler (was calling undefined `handleChatbotInput`), added `/login` + `/signup` route handlers, added `chatbotRenderQuick()` call.
- **bitbot13/auth.js + bitbot13/admin.html + lvl13/admin.html + wallstbots/admin.html**: aligned JWT storage key fallbacks so admin login works across all sites.
- **Footer cross-promo links** standardized to lowercase domain text style across all 3 sites.

### Backend
- **`Backend/main.py`**: `/paypal/webhook` now parses an `origin_platform` field from PayPal `custom`/`custom_id` (format `<site>` or `<site>|ref=CODE`) and writes it to `subscriptions.origin_platform`. PayPal forms on all 3 sites send the site name in `custom`.
- **`Backend/origin_platform_migration.sql`**: adds the `origin_platform` column + check constraint + index. **Applied to production Supabase.**
- **Cloud Run deploy**: revision `wallstbots-backend-00034-8cv` is live at `https://wallstbots-backend-868128114349.us-east1.run.app`.

### Refresh scripts
- **`Project/scripts/refresh_bitbot13.py` + `refresh_wallstbots.py`**: restored truncated content (the previous commit's file was missing the bottom `push_to_api` call section — that's why earlier `--push` runs were silent). Patched to emit canonical signal shape (`symbol`, `action`, `upside_pct`, `target`, `score`, `risk`, `confidence`, `rationale`, `indicators`) so the SPA's signal columns populate correctly. Added crypto-only / stocks-only news source whitelists + topic filters.
- **Both scripts were run successfully** — bitbot13 + wallstbots backends now serve canonical-shape signals and properly-filtered news.

### Docs
- **`SITE_SPEC.md`**: full specification for what each site should be + parity checklist.

---

## ⚠ Pending action items

### 1. Push the latest local code to GitHub (5 sec)
Open PowerShell at `C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots` and run:
```powershell
git add -A
git commit -m "fix: unified login pages, footer link standardization, cross-promo dedup"
git pull --rebase --strategy-option=theirs --autostash origin master
git push origin master
```
This deploys to Cloudflare Pages for bitbot13.tech + wallstbots.tech (~60-90 sec).

### 2. Upload lvl13 to HostGator (most critical)
Files in `C:\Users\temps\OneDrive\Desktop\Claude\Websites\1. lvl13.tech\Project\public_html\` are ready. Upload via cPanel File Manager (URL: `https://sh00167.hostgator.com:2083/cpsess.../frontend/jupiter/filemanager/index.html?dir=lvl13.tech`) — overwrite when prompted:
- `index.html`
- `login.html`
- `assets/app.js`
- `assets/logo.svg`
- `assets/favicon.svg`

Hard-refresh https://lvl13.tech (Ctrl+Shift+R) after upload.

### 3. Daily data refresh (already automated for bitbot13 + wallstbots via GitHub Actions cron)
For a manual refresh now, run from PowerShell:
```powershell
cd C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots
python Project\scripts\refresh_bitbot13.py --push
python Project\scripts\refresh_wallstbots.py --push
```

---

## Known gotchas (the things that wasted a lot of time)

1. **OneDrive sync silently truncates files** mid-write. Symptoms: scripts/files end mid-statement, `node --check` reports `Unexpected end of input`. Always verify after a write with `node --check` (for JS) or `python -m py_compile` (for Python). If a script suddenly stops working silently, check the file length first.
2. **FTP/SFTP blocked from both Cloud Shell and our sandbox** — only your local Windows can reach HostGator's FTP. Don't try to automate this from the cloud.
3. **HostGator FTP requires the cPanel server hostname (`sh00167.hostgator.com`)**, NOT `ftp.lvl13.tech`. The latter doesn't resolve to an FTP server.
4. **HostGator's FTP username** (`178212781`) didn't authenticate via plain FTP from our test — cPanel File Manager works fine. If you ever want CLI FTP, create a per-domain FTP user in cPanel.
5. **The data refresh scripts had been silently truncated in the git repo** — committed without the `push_to_api()` calls. That's why earlier "run the script" attempts produced no output. Now restored.

---

## File reference map

```
WallStBots/
├── SITE_SPEC.md                            # spec for all 3 sites
├── HANDOFF.md                              # this file
├── Backend/
│   ├── main.py                             # FastAPI, deployed to Cloud Run
│   └── origin_platform_migration.sql       # Supabase migration (already applied)
├── Frontends/
│   ├── lvl13.tech/                         # → HostGator (manual upload)
│   ├── bitbot13.tech/                      # → Cloudflare Pages (auto from git push)
│   └── wallstbots.tech/                    # → Cloudflare Pages (auto from git push)
└── Project/
    ├── config/secrets.json                 # gitignored — has FTP, NewsAPI, INTERNAL_API_KEY
    └── scripts/
        ├── refresh_bitbot13.py             # data refresh, --push to write + git push
        └── refresh_wallstbots.py           # same for wallstbots

1. lvl13.tech/Project/public_html/          # staging folder mirroring HostGator layout
```

---

## URLs

- bitbot13.tech — https://bitbot13.tech
- wallstbots.tech — https://wallstbots.tech
- lvl13.tech — https://lvl13.tech
- Backend API — https://wallstbots-backend-868128114349.us-east1.run.app
- Supabase project — `wallstbots-prod` (`rfsssoeyctobxbhpjyom`)
- Cloud Run service — `wallstbots-backend` (us-east1)
- GitHub repo — https://github.com/lvl13tech/wallstbots
- HostGator cPanel — https://sh00167.hostgator.com:2083/

---

*Generated 2026-05-21.*
