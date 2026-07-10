#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ledger_shadow_run.py -- Phase 1/2 shadow runner (LEDGER_REBUILD_ROADMAP_2026-07-10.md).

Run once per day after sessions close (GitHub workflow ledger-shadow.yml, or
manually). For each platform x fund it:

  1. fetches the live /public/tracker/state (cache-busted),
  2. ingests today's published trade_log fills into the shadow ledger
     (append-only, deduped, write-time invariant refusal),
  3. derives cash / positions / total by replaying the ledger,
  4. compares derived numbers against the live displayed numbers,
  5. writes Project/data/ledger_shadow/COMPARE_<date>.txt.

Exit 0 = zero unexplained differences today. Exit 1 = differences or refusals
(each one is either a shadow bug to fix or a live-engine bug the ledger caught
-- both are exactly what Phase 2 exists to surface).

SHADOW ONLY: reads live data, writes only under Project/data/ledger_shadow/.
"""

import os
import sys
import json
import urllib.request
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger_engine import (FundLedger, LedgerRefusal, fills_from_trade_log,
                           SHADOW_DIR)

ROOT = Path(__file__).resolve().parents[2]

# backend url: secrets.json locally, env var in GitHub Actions
BACKEND = ""
sp = ROOT / "Project" / "config" / "secrets.json"
if sp.exists():
    try:
        BACKEND = (json.loads(sp.read_text()).get("api_url") or "").rstrip("/")
    except Exception:
        pass
# same public backend the engines use (not a secret); env/secrets can override
DEFAULT_BACKEND = "https://wallstbots-backend-868128114349.us-east1.run.app"
BACKEND = (os.environ.get("BACKEND_API_URL") or BACKEND or DEFAULT_BACKEND).rstrip("/")

PLATFORMS = {"wallstbots": 55000, "aistocks": 50000, "bitbot13": 50000}
FUNDS = ["bot13", "oracle", "wizard", "equalizer", "titan"]
NOW_ET = datetime.now(ZoneInfo("America/New_York"))
TODAY = NOW_ET.date().isoformat()

# derived-vs-live tolerance: 2dp display rounding compounded across positions
TOL_ABS = 0.05
def tol(x):
    return max(TOL_ABS, abs(x or 0) * 0.0006)


def get(url):
    url += ("&" if "?" in url else "?") + "_lb=" + NOW_ET.strftime("%Y%m%d%H%M%S%f")
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    return json.load(urllib.request.urlopen(req, timeout=30))


lines, diffs, refusals = [], [], []
def log(s=""):
    lines.append(s)
    print(s)


log("=" * 74)
log(f"  LEDGER SHADOW COMPARISON  --  {TODAY} {NOW_ET.strftime('%H:%M ET')}")
log("  (shadow ledger derived numbers vs live displayed numbers)")
log("=" * 74)

for platform, sc in PLATFORMS.items():
    try:
        state = get(f"{BACKEND}/public/tracker/state?platform={platform}")
        data = state["data"]
    except Exception as e:
        log(f"\n[{platform}] FETCH ERROR: {e}")
        diffs.append(f"[{platform}] state fetch failed: {e}")
        continue

    log(f"\n## {platform}  (last_refresh={data.get('last_refresh')})")
    funds = data.get("funds") or {}

    for fund in FUNDS:
        f = funds.get(fund)
        if not f:
            diffs.append(f"[{platform}/{fund}] missing from live state")
            log(f"  [{fund}] MISSING from live state")
            continue
        v = f.get("value") or {}
        scope = f"{platform}/{fund}"

        ledger = FundLedger(platform, fund)
        first_sight = not ledger.meta.get("epoch_date")
        ledger.ensure_epoch(v, float(f.get("starting_capital") or sc), TODAY)

        if first_sight:
            tag = ("clean seed" if not ledger.meta.get("bootstrap")
                   else "BOOTSTRAP (mid-life opening state recorded; replaced at Phase 4 reset)")
            log(f"  [{fund}] epoch opened {TODAY}: {tag}")

        # 1. ingest today's fills.
        # EXCEPTION: on the epoch day itself we ingest nothing -- the epoch is
        # the fund's state as of tonight, which already REFLECTS today's fills;
        # replaying them on top would double-count. Ingestion begins with the
        # next session's fills. (Same principle as the Day-1 rule.)
        fresh = []
        if ledger.meta.get("epoch_date") != TODAY:
            try:
                fresh = ledger.append(
                    fills_from_trade_log(platform, fund, v.get("trade_log")))
            except LedgerRefusal as e:
                refusals.append(f"[{scope}] REFUSED: {e}")
                log(f"  [{fund}] WRITE REFUSED (nothing ingested): {e}")
                continue

        # 2. derive from ledger using live prices
        prices = {p["symbol"]: float(p.get("price") or p.get("current_price") or 0)
                  for p in (v.get("positions") or [])}
        d = ledger.derive(prices)

        # 3. compare derived vs displayed
        rows = [
            ("cash",    d["cash"],    float(v.get("cash") or 0)),
            ("pos_val", d["pos_val"], float(v.get("pos_val") or 0)),
            ("total",   d["total"],   float(v.get("total") or 0)),
        ]
        fund_ok = True
        for name, got, live in rows:
            if abs(got - live) > tol(live):
                fund_ok = False
                diffs.append(f"[{scope}] {name}: ledger {got:.2f} vs live {live:.2f} "
                             f"(diff {got - live:+.2f})")
        # per-position share counts must match exactly.
        # When live pos_val == 0 the fund is all-cash; any listed positions are
        # display leftovers from the day's close-out, not open holdings.
        live_rows = (v.get("positions") or []) if float(v.get("pos_val") or 0) > 0.005 else []
        live_pos = {p["symbol"]: float(p["shares"]) for p in live_rows}
        led_pos = {p["symbol"]: p["shares"] for p in d["positions"]}
        for sym in sorted(set(live_pos) | set(led_pos)):
            a, b = led_pos.get(sym, 0.0), live_pos.get(sym, 0.0)
            if abs(a - b) > 1e-4:
                fund_ok = False
                diffs.append(f"[{scope}] shares {sym}: ledger {a} vs live {b}")

        mark = "OK  " if fund_ok else "DIFF"
        log(f"  [{fund}] {mark} fills+{len(fresh)} (ledger n={len(ledger.fills)}) | "
            f"ledger total {d['total']:.2f} vs live {float(v.get('total') or 0):.2f}")

log("")
log("=" * 74)
if refusals:
    log(f"WRITE REFUSALS ({len(refusals)}):")
    for r in refusals:
        log("  X " + r)
if diffs:
    log(f"DIFFERENCES ({len(diffs)}):")
    for m in diffs:
        log("  X " + m)
    log("")
    log("Each line is either a shadow-ledger bug (fix the ledger) or a live-engine")
    log("bug the ledger caught (fix the engine). Truth = real fill prices.")
else:
    log("RESULT: 0 unexplained differences -- ledger matches live exactly.")
log("=" * 74)

SHADOW_DIR.mkdir(parents=True, exist_ok=True)
report = SHADOW_DIR / f"COMPARE_{TODAY}.txt"
report.write_text("\n".join(lines) + "\n")
print(f"\nreport: {report}")

sys.exit(1 if (diffs or refusals) else 0)
