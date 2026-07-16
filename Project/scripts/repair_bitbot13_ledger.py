"""
One-time LEDGER-LAW repair of bitbot13's BOT13 trade log (2026-07-16).

Replays the stored log through the new ledger law and drops every row that
could never have happened:
  * a SELL with no open lot (the 11:16 phantom MANTA sell)
  * a BUY while the same symbol's lot is already open
Keeps everything else byte-for-byte, order preserved. Backs up the full live
state JSON first. Also repairs the daily_fund_archive copies.
"""
import os, json, datetime, pathlib

import psycopg
from psycopg.rows import dict_row

ROOT = pathlib.Path(__file__).resolve().parents[2]
DB = os.environ.get("DATABASE_URL", "")
if not DB:
    raise SystemExit("DATABASE_URL not set (the .bat loads it from Backend\\.env)")


def repair(log):
    open_syms, out, dropped = set(), [], []
    for e in (log or []):
        a = str(e.get("action", "")).upper()
        s = e.get("symbol")
        if a == "SELL" and s not in open_syms:
            dropped.append(e); continue          # phantom: sold a lot that wasn't open
        if a == "BUY" and s in open_syms:
            dropped.append(e); continue          # phantom: bought an already-open lot
        if a == "BUY":
            open_syms.add(s)
        elif a == "SELL":
            open_syms.discard(s)
        out.append(e)
    return out, dropped


def main():
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    with psycopg.connect(DB, row_factory=dict_row) as conn:
        row = conn.execute("""SELECT id, data FROM tracker_live_data
                              WHERE data_type='state' AND platform='bitbot13'""").fetchone()
        if not row:
            raise SystemExit("No bitbot13 live state found.")
        data = row["data"]
        backup = ROOT / f"bitbot13_state_backup_{stamp}.json"
        backup.write_text(json.dumps(data, indent=2))
        print(f"BACKUP written: {backup}")

        body = data.get("data", data)
        val = (((body.get("funds") or {}).get("bot13") or {}).get("value") or {})
        clean, dropped = repair(val.get("trade_log") or [])
        for e in dropped:
            print(f"  live: dropped phantom {e.get('action')} {e.get('symbol')} @ {e.get('ts')}")
        if dropped:
            val["trade_log"] = clean
            conn.execute("UPDATE tracker_live_data SET data=%s::jsonb WHERE id=%s",
                         (json.dumps(data), row["id"]))
        print(f"live state: {len(dropped)} phantom row(s) removed")

        total = 0
        rows = conn.execute("""SELECT platform, bot_id, fund_name, archive_date, trade_log
                               FROM daily_fund_archive
                               WHERE platform='bitbot13' AND fund_name='bot13'
                                 AND trade_log IS NOT NULL""").fetchall()
        for r in rows:
            clean, dropped = repair(r["trade_log"])
            if dropped:
                conn.execute("""UPDATE daily_fund_archive SET trade_log=%s::jsonb
                                WHERE platform=%s AND bot_id=%s AND fund_name=%s
                                  AND archive_date=%s""",
                             (json.dumps(clean), r["platform"], r["bot_id"],
                              r["fund_name"], r["archive_date"]))
                print(f"  archive {r['archive_date']}: {len(dropped)} phantom row(s) removed")
                total += len(dropped)
        conn.commit()
        print(f"DONE. Backup: {backup.name}")


if __name__ == "__main__":
    main()
