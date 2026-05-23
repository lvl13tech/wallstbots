#!/usr/bin/env python3
"""
reset_fund_data.py
==================
Resets all fund positions for wallstbots.tech and bitbot13.tech to TODAY's
live prices. Every position's entry_price becomes the current price, so
pnl = 0 and pnl_pct = 0 from this point forward.

Run from WallStBots folder:
    python Project/scripts/reset_fund_data.py
"""
import json
import datetime as dt
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed. Run: pip install yfinance")
    raise SystemExit(1)

ROOT        = Path(__file__).resolve().parents[2]
TODAY       = dt.date.today().isoformat()

SITES = {
    "wallstbots": ROOT / "Frontends" / "wallstbots.tech" / "data" / "state.json",
    "bitbot13":   ROOT / "Frontends" / "bitbot13.tech"   / "data" / "state.json",
}

# Crypto symbols need -USD suffix for yfinance
CRYPTO_SYMS = {
    'AAVE','ADA','ALGO','APT','ARB','ATOM','AVAX','BCH','BNB','BTC','CRV',
    'DOGE','DOT','EGLD','ETC','ETH','FIL','FLOKI','FTM','GRT','HBAR','ICP',
    'IMX','INJ','KAS','LINK','LTC','MANTA','MKR','NEAR','NOT','OP','PENDLE',
    'PEPE','QNT','RUNE','SEI','SHIB','SOL','STX','SUI','TAO','THETA','TON',
    'TRX','UNI','VET','WLD','XLM','XRP',
}


def get_yf_ticker(symbol: str, is_crypto: bool) -> str:
    if is_crypto:
        return f"{symbol}-USD"
    return symbol


def fetch_prices(symbols: list, is_crypto: bool) -> dict:
    prices = {}
    print(f"  Fetching {len(symbols)} prices...")
    for sym in symbols:
        ticker = get_yf_ticker(sym, is_crypto)
        try:
            t  = yf.Ticker(ticker)
            fi = getattr(t, "fast_info", None) or {}
            p  = float(fi.get("last_price") or 0)
            if p > 0:
                prices[sym] = p
                print(f"    {sym}: ${p:,.4f}")
            else:
                print(f"    {sym}: no price returned")
        except Exception as e:
            print(f"    {sym}: ERROR - {e}")
    return prices


def reset_positions(positions: list, prices: dict) -> list:
    reset = []
    for pos in positions:
        sym        = pos["symbol"]
        cost_basis = float(pos.get("cost_basis") or 0)
        price      = prices.get(sym)

        if not price or not cost_basis:
            print(f"    SKIP {sym} — no price or cost_basis")
            reset.append(pos)
            continue

        shares = cost_basis / price  # recalc shares at today's price

        reset.append({
            "symbol":      sym,
            "shares":      round(shares, 8),
            "entry_price": round(price, 8),
            "cost_basis":  round(cost_basis, 2),
            "price":       round(price, 8),
            "value":       round(cost_basis, 2),   # value == cost_basis at reset
            "pnl":         0.0,
            "pnl_pct":     0.0,
            "day_pnl":     0.0,
            "day_pct":     0.0,
        })
    return reset


def reset_site(site_name: str, state_path: Path, is_crypto: bool):
    print(f"\n{'='*60}")
    print(f"  Resetting {site_name}")
    print(f"{'='*60}")

    raw        = json.loads(state_path.read_text())
    state_data = raw.get("data", raw)
    funds      = state_data.get("funds", {})
    sc_global  = float(state_data.get("starting_capital", 0))

    # Collect all unique symbols
    all_syms = set()
    for f in funds.values():
        for p in f.get("value", {}).get("positions", []):
            all_syms.add(p["symbol"])

    # Fetch live prices
    prices = fetch_prices(sorted(all_syms), is_crypto)
    missing = all_syms - set(prices.keys())
    if missing:
        print(f"\n  WARNING: no price for {missing} — those positions kept as-is")

    # Reset each fund
    for fid, fund in funds.items():
        sc       = float(fund.get("starting_capital") or sc_global)
        raw_pos  = fund.get("value", {}).get("positions", [])
        cash     = float(fund.get("value", {}).get("cash") or 0)

        print(f"\n  [{fid}] {len(raw_pos)} positions, sc={sc}, cash={cash}")

        new_positions = reset_positions(raw_pos, prices)
        pos_val       = sum(p["value"] for p in new_positions)
        total         = pos_val + cash

        # If bot13 is in cash, keep it fully in cash at sc
        if fid == "bot13" and not new_positions:
            cash  = sc
            total = sc

        fund["inception"] = TODAY
        fund["value"] = {
            "total":     round(total, 2),
            "cash":      round(cash, 2),
            "pos_val":   round(pos_val, 2),
            "pnl":       0.0,
            "pnl_pct":   0.0,
            "day_pnl":   0.0,
            "day_pct":   0.0,
            "positions": new_positions,
        }
        print(f"    → total={total:.2f}  pnl=0.0  positions_reset={len(new_positions)}")

    # Reset snapshots to today only
    today_snap = {"date": TODAY}
    for fid, fund in funds.items():
        today_snap[fid] = fund["value"]["total"]
    state_data["snapshots"] = [today_snap]
    state_data["funds"]     = funds
    state_data["last_refresh"] = dt.datetime.now().isoformat(timespec="seconds")

    # Write back
    out = {"data": state_data}
    state_path.write_text(json.dumps(out, indent=2))
    print(f"\n  ✓ {site_name} state.json reset and saved")


def main():
    print(f"RESET FUND DATA — {TODAY}")
    print("This will reset ALL fund positions to today's live prices.")
    print("pnl and pnl_pct will start at 0.0 from today forward.\n")

    reset_site("wallstbots.tech", SITES["wallstbots"], is_crypto=False)
    reset_site("bitbot13.tech",   SITES["bitbot13"],   is_crypto=True)

    print("\n" + "="*60)
    print("  DONE — both sites reset.")
    print("  Next: run REFRESH-DATA-NOW.bat to push live data,")
    print("  then COMMIT-AND-PUSH-doubleclick-me.bat to deploy.")
    print("="*60)


if __name__ == "__main__":
    main()
