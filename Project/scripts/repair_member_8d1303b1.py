"""
ONE-TIME REPAIR (owner-approved 2026-07-22): member fund 8d1303b1 / bot13.

2026-07-22 incident: under the first hold-the-book build, when part of the
member's book exited, the exited names' cash vanished from the displayed
total (fix already shipped in refresh_portfolios.py). This fund's stored
total was left at the corrupt 6,635.77 (-66%), which the daily carry would
have compounded forever.

Repair: restore total_value to the fund's own last verifiable value —
yesterday's close 19,881.23 (its 2026-07-21 archive row). Today is recorded
as a flat 0% day because its intraday receipts were lost to the display bug;
Rule 0 forbids inventing a day P&L we cannot verify. Backup printed first.
Aborts if the stored state no longer matches what this script expects.

Env: DATABASE_URL (the .bat loads it from Backend/.env)
"""
import os, json
import psycopg
from psycopg.rows import dict_row

EXPECT_BAD   = 6635.77
RESTORE_TO   = 19881.23   # = its own 2026-07-21 archived close (verifiable)

DB = os.environ.get("DATABASE_URL", "")
if not DB:
    raise SystemExit("DATABASE_URL not set")

conn = psycopg.connect(DB, row_factory=dict_row)
cur = conn.cursor()
cur.execute("""select bot_id, total_value, positions, strategy from bot_fund_state
               where bot_id::text like '8d1303b1%%' and fund_name='bot13'""")
row = cur.fetchone()
if not row:
    raise SystemExit("ABORT: fund not found.")
print("BACKUP:", json.dumps({k: str(v) for k, v in row.items()})[:600])
if abs(float(row["total_value"]) - EXPECT_BAD) > 0.01:
    raise SystemExit(f"ABORT: stored total {row['total_value']} != expected corrupt {EXPECT_BAD} — re-audit first.")
ps = row["positions"]
ps = json.loads(ps) if isinstance(ps, str) else (ps or [])
if ps:
    raise SystemExit("ABORT: fund is not flat — refusing to overwrite an open book.")

st = row["strategy"]
st = json.loads(st) if isinstance(st, str) else (st or {})
st["_day_open"] = RESTORE_TO
st["_banked"] = 0.0
st["rationale"] = ("Value restored to the fund's last verifiable close (2026-07-21) after a "
                   "display-accounting bug lost the day's cash carry. No trades were invented.")
cur.execute("""update bot_fund_state set total_value=%s, strategy=%s
               where bot_id::text like '8d1303b1%%' and fund_name='bot13'""",
            (RESTORE_TO, json.dumps(st)))
print(f"Updated {cur.rowcount} row: total {EXPECT_BAD} -> {RESTORE_TO}")
# also correct today's archive row (it recorded the fictitious -66% day)
cur.execute("""update daily_fund_archive set total_value=%s, day_pct=0, day_pnl=0
               where bot_id::text like '8d1303b1%%' and fund_name='bot13'
               and archive_date='2026-07-22' and abs(total_value-%s) < 0.01""",
            (RESTORE_TO, EXPECT_BAD))
print(f"Archive rows corrected: {cur.rowcount}")
conn.commit()
print("REPAIRED. The next member refresh carries forward from the verifiable value.")
