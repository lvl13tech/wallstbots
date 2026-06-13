#!/usr/bin/env python3
"""
reset_lvl13.py
==============
Resets lvl13.tech fund data to a clean slate at today's live prices.
- Builds fresh positions for all 50 stocks at $1,000 cost_basis each
- Starting capital = 50 × $1,000 = $50,000
- All pnl/pnl_pct/day_pnl/day_pct start at 0.0
- bot13 starts in cash (no positions)
- oracle/wizard/equalizer/titan start fully invested (50 positions each)
- Does NOT touch bot_fund_state DB — members area is unaffected

Run from WallStBots folder:
    python Project/scripts/reset_lvl13.py
"""
import json
import datetime as dt
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed. Run: pip install yfinance")
    raise SystemExit(1)

ROOT       = Path(__file__).resolve().parents[2]
STATE_FILE = ROOT / "Frontends" / "lvl13.tech" / "data" / "state.json"
TODAY      = dt.date.today().isoformat()

UNIVERSE = [
    "NVDA","AMD","INTC","ARM","ALAB","MRVL","AVGO","QCOM","SMCI","CRDO","MU","NVTS",
    "MSFT","GOOGL","META","AMZN","ORCL",
    "CRM","NOW","SNOW","DDOG","NET","ZS","OKTA","PATH","PLTR","AI","BBAI","SOUN","UPST","RBRK",
    "PANW","ANET","PSTG","TSLA","ISRG",
    "RXRX","GRAL","SMMT",
    "IONQ","RGTI","QBTS","QUBT","ARQQ","IBM",
    "XNDU","INFQ","HQ",
    "CBRS",
    "SPCX",
]

STARTING_CAPITAL = len(UNIVERSE) * 1000  # $50,000

FUND_ORDER = ["bot13", "oracle", "wizard", "equalizer", "titan"]


def fetch_prices(symbols):
    prices = {}
    print(f"  Fetching {len(symbols)} prices via yfinance...")
    import warnings; warnings.filterwarnings("ignore")
    try:
        import yfinance as yf
        raw = yf.download(symbols, period="5d", auto_adjust=True, progress=False)
        close = raw["Close"] if "Close" in raw.columns else raw
        for sym in symbols:
            try:
                col = close[sym] if sym in close.columns else close
                series = col.dropna()
                if not series.empty:
                    prices[sym] = round(float(series.iloc[-1]), 4)
            except Exception:
                pass
    except Exception as e:
        print(f"  [yfinance batch] error: {e}")

    # Fallback individual fetch for any missed
    missing = [s for s in symbols if s not in prices]
    if missing:
        print(f"  Fetching {len(missing)} missed symbols individually...")
        for sym in missing:
            try:
                t = yf.Ticker(sym)
                hist = t.history(period="5d")
                if not hist.empty:
                    prices[sym] = round(float(hist["Close"].iloc[-1]), 4)
                    print(f"    {sym}: ${prices[sym]}")
                else:
                    print(f"    {sym}: no data")
            except Exception as e:
                print(f"    {sym}: ERROR — {e}")

    print(f"  Got {len(prices)}/{len(symbols)} prices")
    return prices


def make_position(sym, price, cost_basis=1000.0):
    shares = round(cost_basis / price, 8)
    return {
        "symbol":      sym,
        "shares":      shares,
        "entry_price": price,
        "cost_basis":  cost_basis,
        "price":       price,
        "value":       cost_basis,
        "pnl":         0.0,
        "pnl_pct":     0.0,
        "day_pnl":     0.0,
        "day_pct":     0.0,
    }


def make_fund(fid, positions, sc):
    pos_val = sum(p["value"] for p in positions)
    cash    = sc - pos_val
    return {
        "starting_capital": sc,
        "inception":        TODAY,
        "value": {
            "total":     round(sc, 2),
            "cash":      round(cash, 2),
            "pos_val":   round(pos_val, 2),
            "pnl":       0.0,
            "pnl_pct":   0.0,
            "day_pnl":   0.0,
            "day_pct":   0.0,
            "positions": positions,
        }
    }


def main():
    print(f"\n{'='*60}")
    print(f"  RESET lvl13.tech — {TODAY}")
    print(f"  Universe: {len(UNIVERSE)} stocks  |  SC: ${STARTING_CAPITAL:,}")
    print(f"{'='*60}\n")

    prices = fetch_prices(UNIVERSE)
    missing = [s for s in UNIVERSE if s not in prices]
    if missing:
        print(f"\n  WARNING: no price for {missing}")
        print("  Those stocks will be skipped (cash held instead)")

    # Build positions for investable stocks
    investable = [s for s in UNIVERSE if s in prices]
    all_positions = [make_position(s, prices[s]) for s in investable]

    funds = {}

    # bot13 — starts in cash, no positions
    funds["bot13"] = make_fund("bot13", [], STARTING_CAPITAL)
    funds["bot13"]["value"]["cash"] = STARTING_CAPITAL
    print(f"  [bot13]     cash=${STARTING_CAPITAL:,}  positions=0")

    # oracle/wizard/equalizer/titan — fully invested across all stocks
    for fid in ["oracle", "wizard", "equalizer", "titan"]:
        funds[fid] = make_fund(fid, list(all_positions), STARTING_CAPITAL)
        print(f"  [{fid:<10}] total=${funds[fid]['value']['total']:,.2f}  positions={len(all_positions)}")

    # Snapshot
    snap = {"date": TODAY}
    for fid in FUND_ORDER:
        snap[fid] = funds[fid]["value"]["total"]

    state = {
        "data": {
            "platform":         "lvl13",
            "starting_capital": STARTING_CAPITAL,
            "last_refresh":     dt.datetime.now().isoformat(timespec="seconds"),
            "funds":            funds,
            "snapshots":        [snap],
            "leaderboards":     {},
            "signals":          {},
            "news":             [],
        }
    }

    STATE_FILE.write_text(json.dumps(state, indent=2))
    print(f"\n  ✓ state.json written — {len(json.dumps(state))} bytes")
    print(f"  ✓ {len(investable)} stocks loaded, {len(missing)} skipped")
    print(f"\n  Next: commit and push to deploy.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
