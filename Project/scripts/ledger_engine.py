#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ledger_engine.py -- Phase 1 of LEDGER_REBUILD_ROADMAP_2026-07-10.md (SHADOW ONLY).

The permanent data-integrity architecture: an append-only ledger of FILLS is the
single source of truth. Everything else (cash, positions, totals, P&L) is DERIVED
by replaying the ledger -- never stored, never hand-adjusted.

SHADOW MODE: this module writes ONLY to Project/data/ledger_shadow/. It touches
no live tables, no live sites, no existing engines. Fills are ingested from the
live engines' published trade_log (real fills: timestamp, symbol, side, shares,
exact price). Derived numbers are compared against the live displayed numbers by
ledger_shadow_run.py.

Write-time refusal: if appending a batch of fills would violate an invariant
(negative cash, negative shares, zero/negative price), NOTHING is written and
LedgerRefusal is raised. Bad numbers never enter the ledger.
"""

import json
import hashlib
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[2]
SHADOW_DIR = ROOT / "Project" / "data" / "ledger_shadow"

# Cash can accumulate tiny float residue replaying many fills; anything below
# this is treated as zero, anything at or beyond it is a hard violation.
CASH_EPS = 0.005


class LedgerRefusal(Exception):
    """Raised when a write would violate an invariant. Nothing was written."""


# ---------------------------------------------------------------------------
# Tiered price precision (platform standard since 2026-07-10):
#   price < $1    -> 8 decimals
#   $1  - $10     -> 6 decimals
#   above $10     -> 4 decimals
# Storage precision only -- never round a stored fill coarser than its tier.
# ---------------------------------------------------------------------------
def quantize_price(price: float) -> float:
    p = float(price)
    if p < 1:
        return round(p, 8)
    if p <= 10:
        return round(p, 6)
    return round(p, 4)


@dataclass(frozen=True)
class Fill:
    ts: str        # ISO timestamp, ET (as published by the engine)
    platform: str
    fund: str
    symbol: str
    side: str      # BUY | SELL
    shares: float
    price: float   # exact execution price, tier precision

    @property
    def fill_id(self) -> str:
        raw = f"{self.ts}|{self.platform}|{self.fund}|{self.symbol}|{self.side}|{self.shares:.8f}|{self.price:.8f}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    def to_dict(self):
        d = {"ts": self.ts, "platform": self.platform, "fund": self.fund,
             "symbol": self.symbol, "side": self.side, "shares": self.shares,
             "price": self.price, "fill_id": self.fill_id}
        return d


class FundLedger:
    """Append-only fill ledger for one fund on one platform (shadow storage)."""

    def __init__(self, platform: str, fund: str):
        self.platform = platform
        self.fund = fund
        self.dir = SHADOW_DIR / platform
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"{fund}.jsonl"
        self.meta_path = self.dir / f"{fund}.meta.json"
        self.fills = []
        self.meta = {}
        self._load()

    # -- persistence --------------------------------------------------------
    def _load(self):
        if self.meta_path.exists():
            self.meta = json.loads(self.meta_path.read_text())
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                line = line.strip()
                if line:
                    self.fills.append(json.loads(line))

    def known_ids(self):
        return {f["fill_id"] for f in self.fills}

    # -- epoch bootstrap ----------------------------------------------------
    def ensure_epoch(self, live_value: dict, starting_capital: float, today: str):
        """
        The shadow ledger opens an epoch the first time it sees a fund.

        Clean case: the fund sits at starting capital in cash (inception/reset
        state) -> epoch_cash = starting_capital, no opening positions. That is
        the true Day-1 seed and matches the roadmap exactly.

        Bootstrap case: the fund is mid-life (already holds positions / gains).
        We cannot invent its missing history, so we record the observed opening
        state ONCE, labeled bootstrap=true. Forward math from that point is
        fully ledger-derived. The bootstrap epoch is discarded and replaced by
        a true N x $1,000 seed at the Phase 4 full reset.
        """
        if self.meta.get("epoch_date"):
            return
        positions = live_value.get("positions") or []
        cash = float(live_value.get("cash") or 0)
        total = float(live_value.get("total") or 0)
        # After a close-out the feed keeps the day's closed positions listed
        # for display while pos_val == 0. Those are NOT open holdings -- the
        # fund is all-cash. Trust pos_val, not the display list.
        if float(live_value.get("pos_val") or 0) <= 0.005:
            positions = []
            cash = total
        clean = (not positions) and abs(total - starting_capital) < 0.01
        if clean:
            self.meta = {
                "epoch_date": today, "bootstrap": False,
                "epoch_cash": round(starting_capital, 2),
                "epoch_positions": [],
                "starting_capital": starting_capital,
            }
        else:
            self.meta = {
                "epoch_date": today, "bootstrap": True,
                "epoch_cash": round(cash, 2),
                "epoch_positions": [
                    {"symbol": p["symbol"],
                     "shares": float(p["shares"]),
                     "entry_price": quantize_price(p["entry_price"])}
                    for p in positions
                ],
                "starting_capital": starting_capital,
            }
        self.meta_path.write_text(json.dumps(self.meta, indent=1))

    # -- write-time refusal --------------------------------------------------
    def _validate_sequence(self, all_fills):
        """Replay epoch + fills in time order; raise LedgerRefusal on violation."""
        cash = float(self.meta.get("epoch_cash") or 0)
        pos = {p["symbol"]: float(p["shares"]) for p in self.meta.get("epoch_positions") or []}
        for f in sorted(all_fills, key=lambda x: x["ts"]):
            px, sh = float(f["price"]), float(f["shares"])
            if px <= 0:
                raise LedgerRefusal(f"{f['fill_id']}: non-positive price {px}")
            if sh <= 0:
                raise LedgerRefusal(f"{f['fill_id']}: non-positive shares {sh}")
            if f["side"] == "BUY":
                cash -= sh * px
                pos[f["symbol"]] = pos.get(f["symbol"], 0.0) + sh
            elif f["side"] == "SELL":
                have = pos.get(f["symbol"], 0.0)
                if sh > have + 1e-6:
                    raise LedgerRefusal(
                        f"{f['fill_id']}: SELL {sh} {f['symbol']} but ledger holds {have}")
                cash += sh * px
                pos[f["symbol"]] = have - sh
            else:
                raise LedgerRefusal(f"{f['fill_id']}: unknown side {f['side']}")
            if cash < -CASH_EPS:
                raise LedgerRefusal(
                    f"{f['fill_id']}: cash would go negative ({cash:.4f}) after {f['side']} "
                    f"{f['symbol']} -- refusing entire batch")

    def append(self, new_fills):
        """Validate epoch+existing+new as one sequence; on success append only
        the new (deduped) fills. On refusal, nothing is written."""
        known = self.known_ids()
        fresh = [f.to_dict() for f in new_fills if f.fill_id not in known]
        if not fresh:
            return []
        self._validate_sequence(self.fills + fresh)
        with self.path.open("a") as fh:
            for f in sorted(fresh, key=lambda x: x["ts"]):
                fh.write(json.dumps(f) + "\n")
        self.fills.extend(fresh)
        return fresh

    # -- derivation (the only math in the system) ----------------------------
    def derive(self, prices: dict):
        """
        Replay the ledger. Returns cash, open positions (with weighted-average
        entry from actual fills, FIFO-reduced), pos_val, total, realized P&L.
        `prices` maps symbol -> live price for open symbols.
        """
        cash = float(self.meta.get("epoch_cash") or 0)
        # open lots: symbol -> list of [shares, entry_price] (FIFO)
        lots = {}
        for p in self.meta.get("epoch_positions") or []:
            lots.setdefault(p["symbol"], []).append([float(p["shares"]), float(p["entry_price"])])
        realized = 0.0
        for f in sorted(self.fills, key=lambda x: x["ts"]):
            px, sh = float(f["price"]), float(f["shares"])
            if f["side"] == "BUY":
                cash -= sh * px
                lots.setdefault(f["symbol"], []).append([sh, px])
            else:  # SELL, FIFO
                cash += sh * px
                rem = sh
                q = lots.get(f["symbol"], [])
                while rem > 1e-9 and q:
                    take = min(rem, q[0][0])
                    realized += take * (px - q[0][1])
                    q[0][0] -= take
                    rem -= take
                    if q[0][0] <= 1e-9:
                        q.pop(0)
        positions = []
        pos_val = 0.0
        for sym, q in lots.items():
            shares = sum(l[0] for l in q)
            if shares <= 1e-9:
                continue
            cost = sum(l[0] * l[1] for l in q)
            entry = cost / shares
            live = float(prices.get(sym) or 0)
            val = shares * live if live else None
            if val is not None:
                pos_val += val
            positions.append({"symbol": sym, "shares": shares,
                              "entry_price": entry, "cost_basis": cost,
                              "price": live or None, "value": val,
                              "pnl_pct": ((live / entry - 1) * 100) if (live and entry) else None})
        cash = 0.0 if abs(cash) < CASH_EPS else cash
        total = cash + pos_val
        return {"cash": cash, "positions": positions, "pos_val": pos_val,
                "total": total, "realized": realized,
                "bootstrap": bool(self.meta.get("bootstrap")),
                "epoch_date": self.meta.get("epoch_date")}


def fills_from_trade_log(platform: str, fund: str, trade_log: list):
    """Convert an engine's published trade_log rows into Fill records."""
    out = []
    for t in trade_log or []:
        try:
            out.append(Fill(
                ts=str(t["ts"]), platform=platform, fund=fund,
                symbol=str(t["symbol"]), side=str(t["action"]).upper(),
                shares=float(t["shares"]), price=quantize_price(float(t["price"])),
            ))
        except (KeyError, TypeError, ValueError):
            # a malformed row must never silently corrupt the ledger
            raise LedgerRefusal(f"malformed trade_log row for {platform}/{fund}: {t!r}")
    return out
