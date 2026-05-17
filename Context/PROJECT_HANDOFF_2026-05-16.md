# Level XIII Tech — Project Handoff

**Date:** May 16, 2026
**Owner:** Jamil Flowers (M13) · lvl13cs@gmail.com
**Read this first.** It's the state-of-the-world for the next Cowork session.

---

## What's done

### Live and running
- **lvl13.tech** is live, mobile-friendly, and self-updating 24/7
- 5 trading strategies racing on a 43-stock AI/Quantum universe:
  - BOT13 (daily intraday) · ORACLE (weekly Monday) · WIZARD (monthly hold) · EQUALIZER (equal-weight baseline) · TITAN (cap-weighted baseline)
- News feed pulls real stock-relevant headlines from Reuters/Bloomberg/CNBC only (filtered to tracked tickers)
- Chatbot widget + post-purchase form + $799/yr PayPal subscription wired up

### Infrastructure
- **GCP VM** `lvl13-tracker` in `us-east1-c` (project `lvl13-tracker-496402`) runs the tracker engine and 7 cron jobs
- **HostGator Baby Plan** (cPanel user `alxdeqte`) hosts the static site at `/home1/alxdeqte/lvl13.tech/`
- **NewsAPI** key embedded in VM secrets
- **PayPal** subscription form configured for `lvl13cs@gmail.com`
- **Cloudflare** in front of HostGator for the lvl13.tech domain

### Cron schedule on the VM (all ET)
- Every 5 min, 9 AM-4 PM weekdays → refresh prices, snapshot funds, push to lvl13.tech
- 9:32 AM weekdays → BOT13 morning trades, ORACLE Monday rebalance, WIZARD month-start
- 3:56 PM weekdays → BOT13 close-out, WIZARD month-end
- 6 AM & 6 PM daily → news refresh + push
- Sunday 6 PM → weekly auto-graded report
- 12:05 AM daily → end-of-day snapshot

### Marketing assets in workspace folder
- `lvl13_OnePager_v6.pdf` — single-page sales sheet
- `lvl13_Strategy_3Brand_Multitenant.pdf` — 3-page strategy doc for the next phase

---

## What's NEXT (the unstarted work)

The user wants to expand to **3 brands** sharing one backend:
1. **lvl13.tech** — AI & Quantum (current site)
2. **BitBot13** — crypto tracker (new domain TBD, e.g. bitbot13.com)
3. **Wall St Bots** — full NYSE+NASDAQ tracker (new domain TBD, e.g. wallstbots.com)

Goal: when a customer pays $799/yr, their tracker auto-deploys to a private subdomain (`jane.lvl13.tech`, etc) within 2 minutes, fully automatic.

### User's confirmed answers from the strategy planning
- **Build trigger:** Fully automatic (no human touch)
- **Customer access:** Subdomain per customer (recommended in strategy doc)
- **Second HostGator account:** NO — strategy doc recommends NOT buying one. Move toward Cloudflare Pages instead.
- **Scale target:** Build it right; scale will come

### Recommended architecture (per strategy doc, page 1)
- ONE backend serves all 3 brands (single Python codebase, brand config drives differences)
- Each brand = subdomain wildcard DNS via Cloudflare
- Customer subdomain = Cloudflare Pages deploy + Postgres row + cron slice
- PayPal subscription ID = customer identity (no separate login system)

### Phase plan (per strategy doc, page 3)
1. **Week 1:** Refactor tracker into brand-config-driven module, move state to Postgres
2. **Week 2:** Build provisioner FastAPI service + PayPal webhook
3. **Week 3:** Stand up bitbot13.com and wallstbots.com (same codebase, different config)
4. **Week 4:** Migrate lvl13.tech off HostGator entirely → Cloudflare Pages

---

## Critical files & paths

### On the GCP VM (`lvl13-tracker`, user `lvl13cs`)
- `/home/lvl13cs/tracker/RUN_FUND_TRACKER.py` — main tracker engine
- `/home/lvl13cs/tracker/fund_data/fund_*.json` — per-fund state
- `/home/lvl13cs/scripts/refresh_data.py` — pulls live prices, writes state.json
- `/home/lvl13cs/scripts/refresh_news.py` — pulls NewsAPI (whitelist + ticker filter), writes news.json
- `/home/lvl13cs/scripts/deploy_to_hostgator.py` — FTPs all 4 JSON files to lvl13.tech
- `/home/lvl13cs/config/secrets.json` — credentials (NewsAPI key, FTP creds)
- `/home/lvl13cs/public_html/data/*.json` — local mirror before push

### On HostGator (FTP user `tracker@lvl13.tech`, password `LvlTrack_2026!`)
- FTP host: `alx.deq.temporary.site` (port 21, plain FTP — FTPS hangs)
- jailed at `/home1/alxdeqte/lvl13.tech/`
- Site files: `index.html`, `assets/`, `data/`

### Local workspace folder
- `C:\Users\temps\OneDrive\Desktop\Claude\Websites\1. lvl13.tech\Project\` — local copy of site + scripts
- `C:\Users\temps\OneDrive\Desktop\Claude\Apps\2. AI & Quantum Trading App\Project\RUN_FUND_TRACKER.py` — tracker source

### Account credentials referenced
- HostGator billing: customer ID `178212781`, password `TechGiant24$`
- HostGator cPanel SSO works via billing portal → Hosting → Manage → File Manager (no separate cPanel password needed)
- GCP project: `lvl13-tracker-496402`
- Cloud Shell auto-authenticates from the user's logged-in browser session

---

## Known pitfalls (saving the next session from re-discovering them)

1. **OneDrive sync corrupts files.** When writing to anything under `C:\Users\temps\OneDrive\`, files frequently get null bytes injected or get truncated mid-write. Workarounds: write to `/tmp` in bash first, then `cp` to the final location; never trust file size after a Write tool call without re-Read verification.

2. **Cloud Shell terminal needs explicit click before typing.** First click on the terminal to focus, then type. Otherwise the keystrokes go nowhere.

3. **HostGator FTPS hangs from this VM** — use plain FTP (port 21) only. The deploy script is already patched for this.

4. **HostGator Baby Plan blocks shell access** — can't use cPanel Terminal for anything.

5. **cPanel File Manager Ace editor auto-indents Python badly** — use the legacy editor toggle, or just stick to JSON files in cPanel and do Python work via SSH.

6. **SSH-in-browser iframe is sandboxed** — Chrome MCP can't drive it. Use Cloud Shell + `gcloud compute ssh` instead for autonomous installs.

7. **NewsAPI free tier is 100 requests/day, ONE customer.** Going past 1 customer requires paid tier ($449/mo) OR per-customer NewsAPI keys.

---

## Operating preferences (lock these in)

- **No temp fixes that create daily work.** Permanent root-cause fixes only. If a fix can't be permanent in one pass, say so upfront.
- **Senior operator tone.** Execute end-to-end, deliver finished output, push back when something's wrong.
- Match brand voice (see BrandVoice.docx if it exists in workspace).

---

## How to verify everything is still working when you start the new session

```bash
# From any browser
curl -s https://lvl13.tech/data/state.json | python3 -m json.tool | head -20
curl -s https://lvl13.tech/data/news.json | python3 -m json.tool | head -30
```

`last_refresh` in state.json should be recent. News titles in news.json should mention real companies (Nvidia, AMD, IonQ, etc.) from real publishers (Reuters, Bloomberg, CNBC).

If both look good, the live system is healthy and the next phase work can start.
