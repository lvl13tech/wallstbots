#!/usr/bin/env python3
"""
refresh_bitbot13.py
====================
Fetches live crypto prices for the bitbot13.tech 50-coin universe,
enriches all bot positions with P&L, generates trading signals,
fetches crypto news from NewsAPI, and writes the updated static
JSON files to Frontends/bitbot13.tech/data/.

Run daily (or hourly — crypto never closes) on your local Windows machine:
    python Project/scripts/refresh_bitbot13.py

Optional auto-push to GitHub (deploys to Cloudflare Pages):
    python Project/scripts/refresh_bitbot13.py --push

Dependencies:
    pip install yfinance requests
"""

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    import requests as _requests
except ImportError:
    _requests = None

import os   # used to read NEWSAPI_KEY env var in GitHub Actions

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[2]
SECRETS    = ROOT / "Project" / "config" / "secrets.json"
DATA_DIR   = ROOT / "Frontends" / "bitbot13.tech" / "data"
STATE_FILE = DATA_DIR / "state.json"

# ── 50-coin universe ───────────────────────────────────────────────────────────
# Keys are the symbols used in state.json; values are yfinance ticker strings
UNIVERSE_MAP = {
    "BTC":    "BTC-USD",
    "ETH":    "ETH-USD",
    "BNB":    "BNB-USD",
    "SOL":    "SOL-USD",
    "XRP":    "XRP-USD",
    "ADA":    "ADA-USD",
    "TON":    "TON-USD",
    "AVAX":   "AVAX-USD",
    "DOGE":   "DOGE-USD",
    "TRX":    "TRX-USD",
    "LINK":   "LINK-USD",
    "DOT":    "DOT-USD",
    "SHIB":   "SHIB-USD",
    "BCH":    "BCH-USD",
    "NEAR":   "NEAR-USD",
    "UNI":    "UNI7083-USD",   # yfinance uses UNI7083-USD for Uniswap
    "LTC":    "LTC-USD",
    "APT":    "APT21794-USD",  # yfinance uses APT21794-USD for Aptos
    "SUI":    "SUI20947-USD",  # yfinance uses SUI20947-USD for Sui
    "ATOM":   "ATOM-USD",
    "ICP":    "ICP-USD",
    "FIL":    "FIL-USD",
    "ARB":    "ARB11841-USD",  # yfinance uses ARB11841-USD for Arbitrum
    "AAVE":   "AAVE-USD",
    "OP":     "OP-USD",
    "ETC":    "ETC-USD",
    "VET":    "VET-USD",
    "INJ":    "INJ-USD",
    "GRT":    "GRT-USD",
    "ALGO":   "ALGO-USD",
    "XLM":    "XLM-USD",
    "HBAR":   "HBAR-USD",
    "MKR":    "MKR-USD",
    "TAO":    "TAO-USD",
    "STX":    "STX-USD",
    "RUNE":   "RUNE-USD",
    "QNT":    "QNT-USD",
    "KAS":    "KAS-USD",
    "IMX":    "IMX-USD",
    "THETA":  "THETA-USD",
    "WLD":    "WLD-USD",
    "SEI":    "SEI-USD",
    "EGLD":   "EGLD-USD",
    "CRV":    "CRV-USD",
    "FTM":    "FTM-USD",
    "MANTA":  "MANTA-USD",
    "PEPE":   "PEPE24478-USD", # yfinance uses PEPE24478-USD
    "FLOKI":  "FLOKI-USD",
    "PENDLE": "PENDLE-USD",
    "NOT":    "NOT-USD",
}

UNIVERSE   = list(UNIVERSE_MAP.keys())
YF_REVERSE = {v: k for k, v in UNIVERSE_MAP.items()}  # yf_sym → state_sym

FUND_ORDER = ["bot13", "oracle", "wizard", "equalizer", "titan"]

# ── Secrets ────────────────────────────────────────────────────────────────────
def load_secrets():
    if SECRETS.exists():
        return json.loads(SECRETS.read_text())
    return {}

# ── Grading ────────────────────────────────────────────────────────────────────
def grade(pct):
    if pct >= 5:   return "A+"
    if pct >= 3:   return "A"
    if pct >= 1.5: return "B"
    if pct >= 0:   return "C"
    if pct >= -2:  return "D"
    return "F"

def grade_overall(pct, inception_iso, today):
    try:
        inception = dt.date.fromisoformat(str(inception_iso)[:10])
        weeks = max((today - inception).days / 7, 1)
        return grade(pct / weeks)
    except Exception:
        return grade(pct)

# ── Live prices ────────────────────────────────────────────────────────────────
def get_live_prices(state_symbols):
    """
    Fetch live price + previous close for each coin via yfinance.
    state_symbols: list of symbols as they appear in state.json (e.g. ["BTC","ETH",...])
    Returns: (prices dict, prev_closes dict) keyed by state symbol.
    """
    if yf is None:
        print("  [ERROR] yfinance not installed. Run:  pip install yfinance requests")
        return {}, {}

    prices, prev_closes = {}, {}
    print(f"  [yfinance] fetching {len(state_symbols)} crypto tickers...")

    for sym in state_symbols:
        yf_sym = UNIVERSE_MAP.get(sym, f"{sym}-USD")
        try:
            t  = yf.Ticker(yf_sym)
            fi = getattr(t, "fast_info", None) or {}
            p  = float(fi.get("last_price") or 0)
            pc = float(fi.get("previous_close") or 0)
            if p > 0:
                prices[sym]      = p
                prev_closes[sym] = pc if pc > 0 else p
            else:
                # Fallback: try fetching 2-day history
                hist = t.history(period="2d", interval="1d")
                if len(hist) >= 1:
                    p  = float(hist["Close"].iloc[-1])
                    pc = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else p
                    if p > 0:
                        prices[sym]      = p
                        prev_closes[sym] = pc
        except Exception as e:
            print(f"    [warn] {sym} ({yf_sym}): {e}")

    # For any coins that yfinance missed, try CoinGecko (no auth needed, free tier)
    missing = [s for s in state_symbols if s not in prices]
    if missing and _requests is not None:
        print(f"  [coingecko] falling back for {len(missing)} missing coins...")
        _fetch_coingecko(missing, prices, prev_closes)

    print(f"  [yfinance] got {len(prices)}/{len(state_symbols)} prices")
    return prices, prev_closes


def _fetch_coingecko(symbols, prices, prev_closes):
    """
    CoinGecko /simple/price fallback (no API key required for free tier).
    Fills prices / prev_closes in-place.
    """
    # CoinGecko IDs for common symbols — extend if needed
    CG_IDS = {
        "BTC":"bitcoin","ETH":"ethereum","BNB":"binancecoin","SOL":"solana",
        "XRP":"ripple","ADA":"cardano","TON":"the-open-network","AVAX":"avalanche-2",
        "DOGE":"dogecoin","TRX":"tron","LINK":"chainlink","DOT":"polkadot",
        "SHIB":"shiba-inu","BCH":"bitcoin-cash","NEAR":"near","UNI":"uniswap",
        "LTC":"litecoin","APT":"aptos","SUI":"sui","ATOM":"cosmos","ICP":"internet-computer",
        "FIL":"filecoin","ARB":"arbitrum","AAVE":"aave","OP":"optimism","ETC":"ethereum-classic",
        "VET":"vechain","INJ":"injective-protocol","GRT":"the-graph","ALGO":"algorand",
        "XLM":"stellar","HBAR":"hedera-hashgraph","MKR":"maker","TAO":"bittensor",
        "STX":"blockstack","RUNE":"thorchain","QNT":"quant-network","KAS":"kaspa",
        "IMX":"immutable-x","THETA":"theta-token","WLD":"worldcoin-wld","SEI":"sei-network",
        "EGLD":"elrond-erd-2","CRV":"curve-dao-token","FTM":"fantom","MANTA":"manta-network",
        "PEPE":"pepe","FLOKI":"floki","PENDLE":"pendle","NOT":"notcoin",
    }
    need = {s: CG_IDS[s] for s in symbols if s in CG_IDS}
    if not need:
        return
    ids_str = ",".join(need.values())
    try:
        r = _requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ids_str, "vs_currencies": "usd",
                    "include_24hr_change": "true"},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            id_to_sym = {v: k for k, v in need.items()}
            for cg_id, vals in data.items():
                sym = id_to_sym.get(cg_id)
                if sym and vals.get("usd"):
                    p   = float(vals["usd"])
                    chg = float(vals.get("usd_24h_change") or 0) / 100
                    pc  = p / (1 + chg) if (1 + chg) != 0 else p
                    prices[sym]      = p
                    prev_closes[sym] = pc
            print(f"  [coingecko] filled {len([s for s in symbols if s in prices])} coins")
        else:
            print(f"  [coingecko] HTTP {r.status_code}")
    except Exception as e:
        print(f"  [coingecko] error: {e}")

# ── Position enrichment ────────────────────────────────────────────────────────
def enrich_position(pos, prices, prev_closes):
    sym        = pos["symbol"]
    shares     = float(pos.get("shares") or 0)
    entry      = float(pos.get("entry_price") or 0)
    cost_basis = float(pos.get("cost_basis") or (shares * entry))
    price      = prices.get(sym, entry)
    prev       = prev_closes.get(sym, price)
    value      = shares * price
    pnl        = value - cost_basis
    pnl_pct    = (price / entry - 1) * 100 if entry > 0 else 0
    day_pnl    = shares * (price - prev)
    day_pct    = (price / prev - 1) * 100 if prev > 0 else 0

    # Use more decimal places for tiny coins (SHIB, PEPE, etc.)
    price_dp = 8 if price < 0.01 else (4 if price < 1 else 2)
    return {
        "symbol":      sym,
        "shares":      round(shares, 6),
        "entry_price": round(entry, price_dp),
        "cost_basis":  round(cost_basis, 2),
        "price":       round(price, price_dp),
        "value":       round(value, 2),
        "pnl":         round(pnl, 2),
        "pnl_pct":     round(pnl_pct, 2),
        "day_pnl":     round(day_pnl, 2),
        "day_pct":     round(day_pct, 2),
    }

# ── BOT13 crypto daily decision ────────────────────────────────────────────────
def run_bot13_decision(prices, prev_closes, starting_capital):
    """
    Crypto BOT13: rank universe by 24-hr % change, go all-in on top 5 positive movers.
    Crypto trades 24/7 — always looks for edge.
    """
    today_iso = dt.date.today().isoformat()
    scored = []
    for sym in UNIVERSE:
        p  = prices.get(sym, 0)
        pc = prev_closes.get(sym, p)
        if p <= 0:
            continue
        day_pct = (p / pc - 1) * 100 if pc > 0 else 0
        scored.append((sym, day_pct))

    scored.sort(key=lambda x: -x[1])

    # Crypto threshold: lower bar (0.5%) since crypto moves fast
    top_picks = [(sym, pct) for sym, pct in scored[:5] if pct >= 0.5]
    if not top_picks:
        return "CASH", [], []

    per = starting_capital / len(top_picks)
    positions, picks = [], []
    for sym, pct in top_picks:
        price = prices.get(sym, 0)
        prev  = prev_closes.get(sym, price)
        if price <= 0:
            continue
        shares  = per / price
        day_pnl = shares * (price - prev)
        price_dp = 8 if price < 0.01 else (4 if price < 1 else 2)
        positions.append({
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": round(price, price_dp),
            "cost_basis":  round(per, 2),
            "price":       round(price, price_dp),
            "value":       round(shares * price, 2),
            "pnl":         0.0,
            "pnl_pct":     0.0,
            "day_pnl":     round(day_pnl, 2),
            "day_pct":     round(pct, 2),
        })
        picks.append({
            "symbol":    sym,
            "weight":    round(1.0 / len(top_picks), 4),
            "score":     round(pct * 10, 1),
            "rationale": f"{sym}: up {pct:+.2f}% in 24h — positive momentum signal.",
        })

    return "TRADE", positions, picks

# ── Signals ────────────────────────────────────────────────────────────────────
def generate_signals(prices, prev_closes):
    today_iso = dt.date.today().isoformat()
    recs    = []
    summary = {"STRONG BUY": 0, "BUY": 0, "HOLD": 0, "SELL": 0, "STRONG SELL": 0}

    for sym in UNIVERSE:
        p  = prices.get(sym, 0)
        pc = prev_closes.get(sym, p)
        if not p:
            continue
        pct = (p / pc - 1) * 100 if pc > 0 else 0

        if pct >= 5.0:
            signal = "STRONG BUY";  reason = f"Up {pct:+.2f}% in 24h — strong upside momentum."
        elif pct >= 2.0:
            signal = "BUY";         reason = f"Up {pct:+.2f}% in 24h — positive momentum."
        elif pct <= -5.0:
            signal = "STRONG SELL"; reason = f"Down {pct:+.2f}% in 24h — sharp decline."
        elif pct <= -2.0:
            signal = "SELL";        reason = f"Down {pct:+.2f}% in 24h — negative momentum."
        else:
            signal = "HOLD";        reason = f"Flat {pct:+.2f}% — no clear edge right now."

        summary[signal] += 1
        price_dp = 8 if p < 0.01 else (4 if p < 1 else 2)
        recs.append({
            "ticker":     sym,
            "signal":     signal,
            "confidence": round(min(abs(pct) / 10.0, 1.0), 2),
            "reason":     reason,
            "price":      round(p, price_dp),
            "change_pct": round(pct, 2),
            "sector":     "CRYPTO",
            "date":       today_iso,
        })

    recs.sort(key=lambda r: -abs(r["change_pct"]))
    return {
        "recommendations": recs,
        "summary":         summary,
        "generated_at":    dt.datetime.now().isoformat(timespec="seconds"),
    }

# ── News ───────────────────────────────────────────────────────────────────────
def fetch_news():
    """Fetch crypto news from free RSS feeds — no API key, works from GitHub Actions."""
    import xml.etree.ElementTree as ET
    import re
    from email.utils import parsedate_to_datetime

    if _requests is None:
        print("  [news] requests not available — skipping")
        return []

    # Free crypto RSS feeds: (url, sector_tag)
    RSS_FEEDS = [
        ("https://www.coindesk.com/arc/outboundfeeds/rss/",   "BITCOIN"),
        ("https://cointelegraph.com/rss",                     "BITCOIN"),
        ("https://decrypt.co/feed",                           "ETHEREUM"),
        ("https://bitcoinmagazine.com/.rss/full/",            "BITCOIN"),
        ("https://cointelegraph.com/rss/tag/altcoin",         "ALTCOINS"),
        ("https://cointelegraph.com/rss/tag/defi",            "BLOCKCHAIN"),
        ("https://cointelegraph.com/rss/tag/regulation",      "REGULATION"),
        ("https://cointelegraph.com/rss/tag/ethereum",        "ETHEREUM"),
    ]

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; BitBot13/1.0; +https://bitbot13.tech)"
        )
    }

    items, seen = [], set()

    for feed_url, sector in RSS_FEEDS:
        try:
            r = _requests.get(feed_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f"  [news] {sector} HTTP {r.status_code} — {feed_url}")
                continue

            root = ET.fromstring(r.content)
            channel = root.find("channel")
            feed_items = (
                channel.findall("item") if channel is not None
                else root.findall(".//item")
            )

            count = 0
            for itm in feed_items[:6]:
                title = (itm.findtext("title") or "").strip()
                if not title or title in seen or "[Removed]" in title:
                    continue
                desc = re.sub(r"<[^>]+>", "", (itm.findtext("description") or "")).strip()
                url  = (itm.findtext("link") or "").strip()
                pub  = (itm.findtext("pubDate") or "").strip()
                src_el = itm.find("source")
                source = src_el.text.strip() if src_el is not None else feed_url.split("/")[2]
                try:
                    pub_iso = parsedate_to_datetime(pub).isoformat()
                except Exception:
                    pub_iso = pub
                seen.add(title)
                items.append({
                    "title":        title,
                    "description":  desc[:250],
                    "url":          url,
                    "source":       source,
                    "sector":       sector,
                    "published_at": pub_iso,
                })
                count += 1
            print(f"  [news] {sector} from {feed_url.split('/')[2]}: {count} articles")

        except Exception as e:
            print(f"  [news] {sector} {feed_url.split('/')[2]}: {e}")

    items.sort(key=lambda it: it.get("published_at", ""), reverse=True)
    print(f"  [news] fetched {len(items)} total articles")
    return items

# ── Git push ───────────────────────────────────────────────────────────────────
def git_push(msg):
    git_root = Path(__file__).resolve().parents[2]
    try:
        subprocess.run(["git", "-C", str(git_root), "add",
                        "Frontends/bitbot13.tech/data/"], check=True)
        subprocess.run(["git", "-C", str(git_root), "commit",
                        "-m", f"auto: {msg} [{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}]"],
                       check=True)
        subprocess.run(["git", "-C", str(git_root), "push"], check=True)
        print("[git] pushed to GitHub ✓")
    except subprocess.CalledProcessError as e:
        print(f"[git] push failed: {e}")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Refresh bitbot13.tech static data files")
    parser.add_argument("--push", action="store_true",
                        help="Git commit + push after writing (triggers Cloudflare Pages redeploy)")
    args = parser.parse_args()

    secrets     = load_secrets()
    # GitHub Actions passes NEWSAPI_KEY as an env var; secrets.json is for local runs
    newsapi_key = secrets.get("newsapi_key") or os.environ.get("NEWSAPI_KEY", "")

    # ── 1. Load seed state ──────────────────────────────────────────────────────
    print("[bitbot13] loading state.json...")
    raw        = json.loads(STATE_FILE.read_text())
    state_data = raw.get("data", raw)
    funds      = state_data.get("funds", {})
    snapshots  = list(state_data.get("snapshots", []))
    sc_global  = float(state_data.get("starting_capital") or 50000)

    # ── 2. Fetch live prices ────────────────────────────────────────────────────
    need_syms = set(UNIVERSE)
    for fid, fund in funds.items():
        for pos in fund.get("value", {}).get("positions", []):
            s = pos.get("symbol")
            if s:
                need_syms.add(s)

    print(f"[bitbot13] fetching prices for {len(need_syms)} coins...")
    prices, prev_closes = get_live_prices(sorted(need_syms))

    if not prices:
        print("[bitbot13] ERROR: zero prices returned. Check yfinance install and internet.")
        sys.exit(1)

    today_iso = dt.date.today().isoformat()
    now_iso   = dt.datetime.now().isoformat(timespec="seconds")
    today     = dt.date.today()

    # ── 3. BOT13 daily decision ─────────────────────────────────────────────────
    print("[bitbot13] running BOT13 decision...")
    b13_decision, b13_positions, b13_picks = run_bot13_decision(prices, prev_closes, sc_global)
    print(f"  BOT13: {b13_decision} ({len(b13_picks)} picks)")

    # ── 4. Enrich all fund positions ────────────────────────────────────────────
    print("[bitbot13] enriching positions...")
    funds_out = {}

    for fid in FUND_ORDER:
        fund = funds.get(fid)
        if not fund:
            continue
        sc = float(fund.get("starting_capital") or sc_global)

        if fid == "bot13":
            if b13_decision == "TRADE":
                enriched = b13_positions
                cash     = 0.0
            else:
                enriched = []
                cash     = sc

            pos_val = sum(p["value"] for p in enriched)
            total   = pos_val + cash
            pnl     = total - sc
            pnl_pct = (total / sc - 1) * 100 if sc else 0
            day_pnl = sum(p.get("day_pnl", 0) for p in enriched)
            n_pos   = len(enriched)
            day_pct = sum(p.get("day_pct", 0) for p in enriched) / n_pos if n_pos else 0

            value = {
                "total":     round(total, 2),
                "cash":      round(cash, 2),
                "pos_val":   round(pos_val, 2),
                "pnl":       round(pnl, 2),
                "pnl_pct":   round(pnl_pct, 2),
                "day_pnl":   round(day_pnl, 2),
                "day_pct":   round(day_pct, 2),
                "positions": enriched,
            }
            strategy = {
                "day":       today_iso,
                "decision":  b13_decision,
                "rationale": ("Going all-in on today's top 24h momentum names."
                              if b13_decision == "TRADE"
                              else "No positive momentum detected — sitting in cash."),
                "picks": b13_picks,
            }

        else:
            raw_pos  = fund.get("value", {}).get("positions", [])
            enriched = [enrich_position(p, prices, prev_closes) for p in raw_pos]
            cash     = float(fund.get("value", {}).get("cash") or 0)
            pos_val  = sum(p["value"] for p in enriched)
            total    = pos_val + cash
            pnl      = total - sc
            pnl_pct  = (total / sc - 1) * 100 if sc else 0
            day_pnl  = sum(p["day_pnl"] for p in enriched)
            day_pct  = (day_pnl / (total - day_pnl)) * 100 if (total - day_pnl) else 0

            value = {
                "total":     round(total, 2),
                "cash":      round(cash, 2),
                "pos_val":   round(pos_val, 2),
                "pnl":       round(pnl, 2),
                "pnl_pct":   round(pnl_pct, 2),
                "day_pnl":   round(day_pnl, 2),
                "day_pct":   round(day_pct, 2),
                "positions": enriched,
            }
            strategy = fund.get("current_strategy")

        funds_out[fid] = {
            "id":               fid,
            "name":             fund.get("name"),
            "color":            fund.get("color"),
            "icon":             fund.get("icon"),
            "tagline":          fund.get("tagline"),
            "inception":        fund.get("inception"),
            "starting_capital": sc,
            "value":            value,
            "current_strategy": strategy,
            "top10":            fund.get("top10"),
            "per_top_dollars":  fund.get("per_top_dollars"),
            "per_rest_dollars": fund.get("per_rest_dollars"),
        }

    # ── 5. Snapshots ────────────────────────────────────────────────────────────
    today_snap = {"date": today_iso}
    for fid in FUND_ORDER:
        if fid in funds_out:
            today_snap[fid] = funds_out[fid]["value"]["total"]
    snapshots = [s for s in snapshots if s.get("date") != today_iso]
    snapshots.append(today_snap)
    snapshots.sort(key=lambda s: s.get("date", ""))
    snapshots = snapshots[-90:]

    # ── 6. Leaderboards ─────────────────────────────────────────────────────────
    week_start = today - dt.timedelta(days=today.weekday())
    week_cands = [s for s in snapshots if s.get("date", "") <= week_start.isoformat()]
    week_snap  = week_cands[-1] if week_cands else None

    wk_lb, all_lb = [], []
    for fid in FUND_ORDER:
        if fid not in funds_out:
            continue
        v   = funds_out[fid]["value"]
        sc  = funds_out[fid]["starting_capital"]
        sv  = (week_snap or {}).get(fid, sc)
        wp  = v["total"] - sv
        wpc = (v["total"] / sv - 1) * 100 if sv else 0
        wk_lb.append({
            "fund":       fid,
            "week_pnl":   round(wp, 2),
            "week_pct":   round(wpc, 2),
            "week_grade": grade(wpc),
        })
        all_lb.append({
            "fund":          fid,
            "all_pnl":       v["pnl"],
            "all_pct":       v["pnl_pct"],
            "overall_grade": grade_overall(v["pnl_pct"],
                                           funds_out[fid].get("inception", today_iso), today),
        })
    wk_lb.sort(key=lambda r: -r["week_pct"])
    all_lb.sort(key=lambda r: -r["all_pct"])

    # ── 7. Write state.json ─────────────────────────────────────────────────────
    state_out = {
        "data": {
            "starting_capital": sc_global,
            "last_refresh":     now_iso,
            "snapshots":        snapshots,
            "funds":            funds_out,
            "leaderboards":     {"week": wk_lb, "all": all_lb},
        }
    }
    STATE_FILE.write_text(json.dumps(state_out, indent=2))
    print(f"[bitbot13] ✓ state.json  — {len(funds_out)} funds, {len(snapshots)} snapshots")

    # ── 8. Write signals.json ───────────────────────────────────────────────────
    signals = generate_signals(prices, prev_closes)
    (DATA_DIR / "signals.json").write_text(json.dumps({"data": signals}, indent=2))
    n_sig = len(signals["recommendations"])
    print(f"[bitbot13] ✓ signals.json — {n_sig} signals  "
          f"(BUY:{signals['summary']['BUY']+signals['summary']['STRONG BUY']}  "
          f"HOLD:{signals['summary']['HOLD']}  "
          f"SELL:{signals['summary']['SELL']+signals['summary']['STRONG SELL']})")

    # ── 9. Fetch + write news.json ──────────────────────────────────────────────
    print("[bitbot13] fetching news...")
    news_items = fetch_news()
    all_sectors = sorted({it["sector"] for it in news_items}) or [
        "BITCOIN","ETHEREUM","ALTCOINS","REGULATION","BLOCKCHAIN","SECURITY",
    ]
    news_out = {
        "data": {
            "items":        news_items,
            "sectors":      all_sectors,
            "generated_at": now_iso,
        }
    }
    (DATA_DIR / "news.json").write_text(json.dumps(news_out, indent=2))
    print(f"[bitbot13] \u2713 news.json   \u2014 {len(news_items)} articles")

    # \u2500\u2500 10. Git push (optional) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    if args.push:
        print("[bitbot13] pushing to GitHub...")
        git_push("bitbot13.tech data refresh")


if __name__ == "__main__":
    main()
