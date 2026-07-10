# PROJECT_STATUS.md — What Works and What's Broken

**Keep this file honest and current.** Update it at the end of every work session.
When Claude finishes a change, the LAST step is to update this file.

Last updated: 2026-07-08 — EMPTY-SITE INCIDENT (audit caught it): bitbot13's live state has been
EMPTY (funds {}) since shortly after the clean reset, refreshed every cycle by a runner that is
NOT this folder (this folder's disk state.json is still the pristine reset blob — a healthy run
rewrites it every cycle). Evidence points to a second checkout (old deploy scripts reference
C:\Users\temps\OneDrive\Desktop\Claude\Websites\1. Wall St Bots) running OLD engine code whose
worst path is: disk empty/corrupt + one API-fallback failure -> "using empty state" -> publishes
an empty site -> writes the empty blob to its own disk -> feeds on its own poison forever. That
runner also starves the member sims (bitbot13 member states stale).
FIX (code, this folder): EMPTY-STATE GUARD in all 3 engines — a parsed-but-fundless disk state
falls back to the live API; if the API also has no funds the run ABORTS (exit 1). An engine can
never publish an empty site again. NOT YET PUSHED — RUN-PUSH-EMPTYGUARD.bat.
OWNER ACTIONS (in this order): 1) Task Scheduler: find the bitbot13 refresh task; repoint it to
C:\Claude\Websites\WallStBots (or disable the old-checkout task entirely — the rogue runner will
otherwise keep re-poisoning bitbot13 no matter what we reset). 2) RUN-PUSH-EMPTYGUARD.bat.
3) RUN-RESET-BITBOT13.bat to restore bitbot13's clean baseline. wallstbots + aistocks audited
CLEAN after their first real trading day.

---

Previous: 2026-07-07 — SECOND-PASS AUDIT ROUND (owner rule: "on resets there is no old data;
resets and new member portfolios never call on yesterday's data"). Second sweep verified clean:
tracker push = full replace, git can't resurrect state (data files gitignored), engine day-math
helpers read only the reset-seeded baseline, member creation path clean. Three leftovers fixed:
R1 **Resets now HARD-DELETE all old member data in the DB** (Backend/main.py — needs deploy via
   DEPLOY-BACKEND-ROOTCAUSE.bat): the wipe endpoint also deletes the member report archive
   (daily_fund_archive platform='member' — it fed member monthly statements with corrupt-era
   rows and had no reset pruning, unlike the public archive which self-prunes to inception);
   and ANY pending restart arriving at the upsert (full reset OR repair) deletes that fund's
   prior-day archive rows + the portfolio's prior-day performance snapshots. Deploy is image-
   only (env vars preserved).
R2 **Baseline funds enter at LIVE prices**: equalizer/titan seeds (3 engines) and the member
   baseline builder used the PREVIOUS DAY'S CLOSE as entry — day 1 showed an overnight gap the
   fund never held. All entries everywhere are now the live price at entry time; unpriceable
   symbols stay as cash and self-seed at their first real price.
R3 **Legacy state-writers retired**: fix_bitbot13_source.py and reset_lvl13.py now refuse to run
   (both could inject old-era state if ever run again). One reset tool remains: full_reset_all.py.
R4 OWNER ACTION: confirm Windows Task Scheduler only runs the intended refresh scripts.
Deploy order: RUN-PUSH-SECONDPASS.bat → DEPLOY-BACKEND-ROOTCAUSE.bat (Docker Desktop + gcloud
login required) → optional full_reset_all.py --all for a clean day 1.

---

Previous: 2026-07-07 — ROOT-CAUSE FIX ROUND (owner-directed: "fix everything correctly, no
patches"). WHY DATA KEPT RE-CORRUPTING AFTER 7 DAILY RESETS — all causes found and fixed:
1) **The reset tool itself corrupted members**: full_reset_all.py LAYER 2 wrote the PLATFORM's
   capital ($55k/$50k) into every member portfolio instead of the member's own N×$1,000 —
   every daily reset re-planted the +175%-style fictitious gains, and then reseeded each
   member's day-0 history row from that wrong number. FIXED: members reset at their own
   N×$1,000 in the engine's PENDING shape (first real entries next session; engines honor it).
2) **aistocks resets were deterministically resurrected**: the reset skipped aistocks' disk
   state.json ("backend-driven" was wrong — ALL 3 engines read disk FIRST and push it back).
   FIXED: LAYER 3 now writes clean disk for all three platforms.
3) **Reset-collision race**: engines load state, compute for minutes, push at the end — a
   reset in that window was overwritten by the in-flight run (bitbot13 refreshes 24/7, so
   near-guaranteed there). FIXED: shared reset_occurred_mid_run() guard in bot13_engine.py —
   each engine re-checks fund inceptions on the backend just before its write/push and
   ABANDONS the whole run if a reset happened mid-flight (no disk write, no pushes, no member
   sims). Fails open only if the backend is unreachable.
4) **Stale day_boundary**: reset now removes the prior-day price block — day 1 references NO
   prior-day data anywhere.
5) **full_reset_bitbot13.py retired**: it carried the same platform-capital member bug; it now
   refuses to run and points to full_reset_all.py --platform bitbot13 (one reset path only).
Member portfolio CREATION verified clean end-to-end (own N×$1,000, PENDING, first entries next
session). Audit's STARTED-AT check (entry_cost == N×$1,000) would now catch a reset-tool
regression the same day. NOT YET PUSHED — RUN-PUSH-ROOTCAUSE.bat.

---

Previous: 2026-07-06 midnight — ROUND 3 (owner-directed, numbers only): the last audit red
was the bot13 Strategy-box prose after close. Owner spec: HOLD = no-edge days only; TRADE days
keep the frozen, dated strategy box until the next trading day; "Session complete" prose is fine.
Fixes: (1) the after-hours "graceful fallback" in all 3 engines now fires ONLY on a genuinely
broken chain (stored strategy from a DIFFERENT day) — it was re-firing every post-close refresh
and shuffling the frozen box (TRADE/HOLD oscillation). (2) The audit's prose/cards check is now
a WARN that fires only when the prose names a DIFFERENT known symbol than the cards (stale-story
signal); generic prose naming nothing is fine — words, not numbers. Verified live: bitbot13 now
PASSES; whole system has zero failures (only the XRP 2dp display notes, which clear when round-2
precision takes effect at the next session's entries). NOT YET PUSHED — RUN-PUSH-ROUND3.bat.

---

Previous: 2026-07-06 late night — ROUND 2 (owner-approved): bitbot13 kept trading after the
member repair and the audit caught a re-corruption within the hour. Root causes fixed:
1) ENGINE now HONORS a stored PENDING state until its starts_on date (previously only
   creation-day portfolios waited, so repaired funds re-seeded mid-session) — refresh_portfolios.py.
2) Titan's own inception block still fabricated $1.00 entries after the shared builder was fixed
   (BNC/NOTE/POL/SAFE/XEC caught live) — now skips unpriced coins; they seed at their first real price.
3) Entry-price precision: engine stores entries at tiered decimals (8dp sub-penny, 6dp <$1, 4dp <$10)
   and computes shares from the ROUNDED entry so cost == shares × entry exactly (VET 1% drift fixed).
   refresh_bitbot13.py seeding tiers matched.
4) DISPLAY (owner request): Entry/Price columns show the full stored precision on bitbot13 ONLY
   (fmtCrypto re-tiered in its app.js/portfolio-fund/bot-detail — >=$10 2dp, >=$1 4dp, >=1c 6dp,
   sub-penny 8dp). wallstbots/aistocks are strictly stocks (owner) — their display files were NOT
   touched this round (fmtCrypto is bitbot13's existing allowed asset-class difference).
5) Audit sign checks now require a meaningfully nonzero percentage (a −$2.42 day rounding to
   0.00% is not a sign disagreement). JUP needed no alias — the platform map already carries it.
DEPLOY: RUN-PUSH-ROUND2.bat, then RUN-REPAIR-MEMBERS.bat again (TopCryp re-corrupted tonight;
the PENDING gate — already live locally since engines run from this working copy — holds the
restart until the next session this time). NOTE: bot13 rationale/picks prose mismatch on rotation
(public bitbot13) is a separate open item, not yet investigated.

---

Previous header: 2026-07-06 night — DATA-INTEGRITY FIX ROUND COMPLETE. Pushed (commit b38406d),
member repair APPLIED (15 fund-states restarted portfolio-wide per owner rule — dry-run +
before/after in RUN-REPAIR-MEMBERS_LOG.txt), and the full audit is GREEN: exit 0, zero
failures on all 3 platforms including the member section. Independently re-verified against
the live backend from the workbench. Remaining warnings only: aistocks 49/50 (clears when P
tops up at the next session open) + benign 2dp display-rounding notes on sub-$2 coins.
Small follow-up to commit: repair_member_states.py gained network retries + the
PORTFOLIO-WIDE RESET rule after the main push — RUN-PUSH-REPAIR-TWEAKS.bat.

---

**2026-07-06 (late) — Full data-integrity fix round (owner-approved item by item). NOT YET PUSHED.**
Deploy order: 1) RUN-PUSH-INTEGRITY-FIXES.bat (commit+push everything) → 2) wait for the next
scheduled refresh (or run one) so the fixed engines write fresh states → 3) RUN-REPAIR-MEMBERS.bat
(one-time; dry-run report, then applies, then re-audits) → 4) RUN-AUDIT.bat any time after.

- **A1 — Dead scaling code deleted** (`refresh_portfolios.py`): the old "member dollars scaled
  from the platform" block and its false "confirmed correct" docstring are gone. The engine was
  already independent (dollars from the member's own positions); this removes the trap.
- **A2 — Crypto price parity** (`refresh_portfolios.py`): member coin prices now fetched with the
  SAME Yahoo ticker mapping as the platform engine (ADA→ADA-USD, UNI→UNI7083-USD…, TRON→TRX-USD,
  fallback SYM-USD). Root cause of bitbot13 member equalizer −37% fiction. Also: an unpriceable
  symbol is now NEVER seeded at a fabricated $1.00 entry — it stays as cash and seeds itself at
  the first real price; its cash stays in the fund total (baselines).
- **A2b — aistocks members ran the CRYPTO engine** (`refresh_portfolios.py`): "aistocks" was
  missing from PLATFORM_CFG, so member BOT13 on aistocks used crypto logic and crypto hours.
  Added the equity entry. (Standalone CLI choices also gained "aistocks".)
- **D — PSTG → P** (`refresh_aistocks.py`): Pure Storage rebranded to Everpure; ticker changed
  PSTG→P (Apr 2026) which killed the feed — that was the missing 50th stock (SPCX is fine and
  trading). Universe renamed. Plus **BASELINE TOP-UP** in all 3 public engines: a universe symbol
  missing from an already-seeded equalizer/titan enters at the next open session's real price
  with its idle per-slot dollars ($1,000 idle on aistocks eq + titan gets deployed next session).
- **B — Audit member checks rewritten for independent sims** (`audit_integrity.py`): LOCKSTEP
  (which assumed the old scaling engine) replaced by: OWN-POSITIONS (member total == sum of its
  own holdings + baseline idle cash), per-position derivations, fabricated-$1.00-entry signature,
  price/entry sanity band, IMPOSSIBLE MOVE derived from (total − _day_open)/_day_open (the
  internal endpoint carries no day_pct), PLATFORM-DOLLAR-LEAK signature. Verified live: 25
  failures across the 3 platforms, all pointing at the 7 known-corrupt member fund-states +
  their fabricated positions; every healthy state passes.
- **A3 — One-time repair** (`repair_member_states.py` + RUN-REPAIR-MEMBERS.bat): detects corrupt
  member fund-states by signature (leak / impossible move / fabricated $1 entries / not-own-
  derived / impossible carry >1.5×cost) and restarts ONLY those at the member's own N×$1,000,
  trading begins next session. Dry-run verified live: flags exactly 7 (DoubleUp b13/oracle/
  wizard, NextTech b13, TopCryp b13/equalizer/titan), keeps the 8 healthy ones. NOTHING deleted —
  old rows/snapshots remain as the audit trail; charts era-guard at the repair boundary.
- **C — Frontends, identical ×3 sites**: bot-detail chart now plots the member's OWN history
  (was: platform history rescaled to member capital — forbidden pattern on display); bot-detail
  My-Holdings Entry/Current now read from the member's own equalizer fund state (bot_holdings
  carries no prices — every row showed "—"); leaderboard.html no longer hardcodes "+" (negative
  returns render correctly in red).
- **Known-good vs untested:** audit + repair-detection verified against live data from here.
  Engine changes compile-gated in the push .bat (sandbox mirrors were NUL-corrupted, so compile
  runs Windows-side at commit time). Frontend changes need a browser once deployed: bot-detail
  chart title reads "Performance Trajectory — Your Portfolio", holdings show real Entry/Current.
- **Open (optional, needs owner call):** a tiny internal GET for member history snapshots would
  let the audit verify member charts point-by-point; internal fund-state endpoint could also
  return day_pnl/day_pct so the audit checks the stored values directly.

---

**2026-07-06 (evening) — Visual walkthrough of all 3 sites + audit hardening. AUDIT-ONLY CHANGE (one file: Project/scripts/audit_integrity.py). NOT YET PUSHED — RUN-PUSH-audit-hardening.bat.**
- **Walkthrough result: all 3 PUBLIC sites reconcile perfectly** (every box vs every box:
  value=cash+holdings, P&L=value−start, today=value−prior close, holdings sums, leaderboard,
  chart last point, BOT13 trade-history ledger). Home/race/fund pages share one data fetch,
  so they cannot drift from each other.
- **MEMBER data is corrupted on all 3 sites and the old audit could not see it** (it only
  checked that member numbers agreed with each other, and corrupt numbers can be internally
  consistent). Live examples found on the pages members see: DoubleUp (wallstbots, $20,000
  start) shows $72,110 / +260.55% all-time / +31.11% today while platform BOT13 is +4.23%;
  NextTech (aistocks) +120.96% today; TopCryp (bitbot13) equalizer −37%. Root signature:
  PLATFORM-scale dollars ($55,000/$50,000 day-opens) stored inside member records + stale
  pre-reset carries. The member engine (refresh_portfolios.py) computes member dollars by
  SCALING from the platform tracker, so member pct must equal platform pct — divergence = corrupt.
- **New audit checks added (all verified firing on the live data — 20 FAILURES, 4 new WARNs):**
  LOCKSTEP (member pct must equal platform pct), PLATFORM-DOLLAR LEAK (member day_open must be
  on the member's own N×$1,000 scale), STARTED-AT (entry_cost = N holdings × $1,000), STALE
  STATE (member state must be same-day on a trading day), BOT13 INTRADAY CASH (cash = day_open −
  deployed + realized, verified live on bitbot13 mid-session), BASELINE DEPLOYMENT (equalizer/
  titan must hold the whole universe — caught aistocks equalizer AND titan at 49/50 with
  ~$1,000 idle each), plus a CACHE-BUSTER on every audit fetch (an edge cache served an
  18-hour-old state to an off-site audit run — audits must always judge live data).
- **Known-good vs untested:** public-site data verified clean (live). New audit checks verified
  firing (live). The MEMBER DATA ITSELF is still corrupt — the audit now reports it, nothing
  repairs it. Repair is an engine/data decision the owner must approve separately.
- **Owner decisions still open (NO changes made):**
  1. The scaling formula in refresh_portfolios.py itself conflicts with Rule 0 (a portfolio
     activated mid-era inherits the platform's since-reset gains). Keep scaling or switch
     members to true independent sims? The audit documents both modes (see its docstring).
  2. bot-detail.html trajectory chart draws PLATFORM history rescaled to member capital
     (display-only Rule 0 concern, all 3 sites).
  3. Member history (bot_performance_snapshots) has no internal read endpoint, so the audit
     cannot yet verify member charts (DoubleUp's history shows $55,000 flat on 7/04–7/05 on a
     $20,000 portfolio — visible corruption with no automated check). A tiny internal GET
     would close this.
  4. leaderboard.html hardcodes a "+" before gain_loss_pct (would render "+-3.00%" if a
     negative ever ranks).
- Sandbox mirror note: audit_integrity.py was served TRUNCATED (474 of 640 lines) by the sync
  layer during this session — Windows-side file is complete and compile-gated in the push .bat.

---

(previous header, kept for history)
2026-06-28 (BOT13 Today's-Strategy + Trade-History fixes built+verified, NOT YET PUSHED — DEPLOY-bot13-strategy-tradehistory_2026-06-28.bat)
`refresh_lvl13.py`, `refresh_bitbot13.py` — written and verified locally, **NOT YET
COMMITTED/PUSHED**) ·
Status: **CODE FIXED AND COMPILE-VERIFIED ON ALL 3 PRODUCT SITES. Owner still needs to run
the git commit/push step (see ".bat to run" below) before any live site picks this up.** ·

---

**2026-07-05 — Account-drawer duplication permanently fixed (bot-detail.html + portfolio-fund.html, all 3 sites). DEPLOYED (commit 927e3b8, pushed to master).**
Deploy: DEPLOY-account-drawer-dedup_2026-07-05.bat (repaired mid-session — see note below).
- Root cause: bot-detail.html and portfolio-fund.html each carried their own hand-copied,
  stale "My Account" drawer (no Invite & Earn, no admin codes, no email prefs), separate
  from dashboard.html's real implementation. Every account-drawer fix made this session
  (JWT refresh, admin-invite role check) only ever reached dashboard.html.
- Fix: bot-detail.html (3 sites) — My Account is now a plain link to dashboard.html (same
  pattern leaderboard.html already used). portfolio-fund.html (3 sites) — duplicated
  Profile/Referral/Reset-Password sections replaced with one "Manage Account & Referrals"
  link; page-specific Portfolio Settings (privacy/leaderboard/share toggles) kept in place.
  One real account drawer per site now, zero duplicates. 6 files, 60 insertions(-456
  deletions).
- Script note: the first version of the deploy script had a cmd.exe quoting bug in a
  verification step (embedded `\"` inside a double-quoted argument silently swallowed
  later script lines with no visible error) — its first run did NOT commit/push despite
  printing PASS. Repaired: removed the broken step, added a hard post-commit check
  (verifies HEAD subject actually mentions "account drawer", BLOCKS otherwise). Re-run
  confirmed real: fb898c2..927e3b8 pushed, log matches expected commit hash.
- Frontend-only change; Cloudflare Pages auto-deploys on push, no Cloud Run step needed.
- **Still untested (owner to verify):** click My Account on bot-detail.html AND
  portfolio-fund.html on all 3 sites -> lands on dashboard.html's Invite & Earn panel;
  portfolio-fund.html's own Portfolio Settings toggles still open/work from their drawer.
- Not yet actioned: cosmetic `alt="AI Stocks"` clone artifact on wallstbots.tech's
  portfolio-fund.html logo image (flagged, lower priority).

---

**2026-06-28 — BOT13 Today's Strategy + Trade History fixes. Built + verified locally, NOT YET PUSHED.**
Deploy: DEPLOY-bot13-strategy-tradehistory_2026-06-28.bat. All 3 sites + member pages.
- Edge Score: close-out branches no longer zero b13_proj/rationale; they preserve the morning
  values. Strategy box decision shows TRADE (display) once traded_today; HOLD only on a true
  no-trade day. Killed the "HOLD -- daily close-out ... flattened" message.
- Trade History: ledger now diffs REAL accounting positions via a separate _real_positions key
  (display-freeze positions were injecting phantom BUY/SELL rows). TODAY-ONLY log: resets each
  new ET day (also clears old phantom rows on first run). Every traded asset = BUY + matching
  SELL by EOD. Sort: chronological during day (9:30am first); after close, BUY->SELL pairs
  ordered by earliest buy time. Colors: BUY blue; SELL green if profit, red if loss.
- Members (refresh_portfolios.py): same real-position diff + daily reset.
- RECOVERY note: refresh_lvl13.py + refresh_bitbot13.py were NUL-corrupted (623 NULs each,
  OneDrive/checkout) -> restored from git + NUL-stripped + refixed via Python. wallstbots was
  truncated earlier, restored + refixed. Deploy .bat has a NUL-byte gate now.
- Audit doc: AUDIT_BOT13_STRATEGY_BOX_TRADED_VS_NOT_2026-06-28.md.
- DEFERRED (next, separate): aistocks rename (refresh_lvl13.py -> refresh_aistocks.py);
  email still-not-sending follow-up (PARKED).

---

**2026-06-24 — FULL MEMBER-EMAIL REBUILD. Built + verified locally, NOT YET PUSHED.**
Implements the owner's complete email blueprint (six email types), all at once.
- **Root cause of the multi-day outage (confirmed):** the morning send was gated on
  `HOUR=13 && MIN<45` UTC — only the single 13:30 cron tick matched; a dropped tick (GitHub
  best-effort cron) = no email, and cron-job.org backups didn't help because the workflow
  re-checked the same minute-gate. Manual workflow_dispatch sent fine, proving Resend/domain
  were never the problem. FROM stays info@lvl13.tech (owner confirmed).
- **New design:** all gating moved OUT of YAML into `send_emails.py --kind {open,trade,
  close-stock,close-crypto}` with per-kind once-per-ET-day markers (committed under
  Frontends/wallstbots.tech/data/.email_*_sent). Immune to dropped ticks + double-sends.
  wallstbots owns weekday open + stock close-out + trade alerts; bitbot13 owns weekend open
  (--weekend-only) + crypto trade alerts + crypto close-out; lvl13 sends nothing.
- **Six emails:** weekday open (member + all 3 sites decisions/signals); weekend open
  (member + BitBot13, "market closed" notice for stocks); intraday trade alert (one per
  refresh-with-activity); stock close-out 3:30pm (member+wallstbots+aistocks sells); crypto
  close-out 9pm (member+bitbot13 sells). New templates in email_service.py.
- **Per-member trade detection:** refresh_portfolios.py now diffs each member's BOT13
  trade_log/positions vs prev_states -> traded_today/closed_out; Backend bot_fund_state
  gained traded_today/closed_out columns; /admin/email-subscribers now returns per-member
  bot13_activity_<platform> so each member's own buys/sells appear in their alerts.
- **Aistocks section fixed:** send_emails.py reads aistocks from the backend API (was the
  dead Frontends/lvl13.tech/data path).
- **Verified:** all .py py_compile clean; 3 workflows valid YAML; dispatch unit-tested
  (weekday open->"Daily", repeat->skip via marker, trade, both close-outs; weekend
  open->"Weekend Crypto", close-stock skips); every template renders real HTML with fake
  member activity.
- **Deploy:** `DEPLOY-email-rebuild_2026-06-24.bat` (one-click, logged; guard+compile+YAML
  gates, commit/merge/push; pushing Backend/** auto-deploys Cloud Run). NOT RUN YET.
  Post-deploy: workflow_dispatch on Refresh wallstbots (passes --force) to test live.
- Supersedes the earlier partial send-once fix from this date.

---

**2026-06-24 (later session) — BOT13 page during-vs-after trading-hours fix (Box C/D/E/F),
all 3 sites + member pages. CODE COMPLETE & VERIFIED LOCALLY, NOT YET PUSHED.**
Owner reported the BOT13 fund page (public `#/fund/bot13` and the member `portfolio-fund.html`)
stopped behaving correctly after the Trade History timestamp box was added.
- **Box F (Trade History):** now sorts CHRONOLOGICALLY while the session is open, and
  A-Z by symbol (BUY before SELL per symbol) after close. Sorting is display-only on a COPY
  of the immutable `trade_log` (frontend `sortTradeLog()`), so the ledger can never be
  reordered/corrupted and a missed refresh can't show a stale order. Now BOT13-ONLY: removed
  `stamp_and_log` from the per-fund loop for oracle/wizard/equalizer/titan in all 3 public
  engines AND `refresh_portfolios.py` (baselines were emitting phantom BUY/SELL/RESIZE rows
  from the >2% share-drift rule — the "broke other areas" cause). No longer hidden on a cash
  day — shows "No trades today".
- **Boxes C/D/E freeze after hours, reset at next open.** Engine now preserves the day's
  closed-out positions READ-ONLY in `value.positions` + a new `traded_today` flag (display
  only — flat total/pnl accounting untouched). Box C holds value-at-close (bitbot13 recomputes
  realized day P&L since crypto HOLD uses day_open; equity already carried prev_b13_total).
  Box D shows the picks + "TRADED — closed for the day" instead of a HOLD/CASH card on days it
  traded (HOLD card only on true no-trade days). Box E keeps the day's assets with summary row
  "End of trading — now holding cash" (traded) or "Holding cash - no trades made today" (none).
- **Files:** 6 frontend (`assets/app.js` + `portfolio-fund.html` × wallstbots/aistocks/bitbot13;
  bitbot13 keeps "Units" header, others "Shares") + 4 engines (`refresh_wallstbots.py`,
  `refresh_lvl13.py` = aistocks engine, `refresh_bitbot13.py`, `refresh_portfolios.py`).
  lvl13.tech corporate landing NOT touched.
- **Truncation recurrence:** during this session the Edit tool truncated all 10 files mid-save
  again (caught by py_compile + node --check; the Read tool had cached full-length views,
  masking it). Recovered via `RESTORE-truncated-bot13-files_2026-06-24.bat` (git checkout) and
  re-applied every edit through bash+Python writes (proven non-truncating), verifying each file
  on disk after every write.
- **Verified:** all 5 .py `py_compile` clean; all 3 app.js pass `node --check`; parity shas
  match across sites; truncation guard (HTML + .py) passes.
- **.bat to run:** `DEPLOY-bot13-hours-fix_2026-06-24.bat` (one-click, logged, runs guard +
  compile gate first, then commit/merge/push). Live data corrects on the next 15-min refresh.

---

**2026-06-24 — Real regression found and fixed: "Today's Strategy" box on the BOT13 fund
page fell back to the generic "Market closed -- waiting for next trading session." message
on days BOT13 actually traded.** Owner's proof point: `bitbot13.tech/#/fund/bot13` was
showing the real trade story (`TRADE`, "Deployed into 1 coins with momentum + volume
confirmation (RUNE +3.73%)...") because bitbot13's BOT13 still had an open position today,
while `wallstbots.tech/#/fund/bot13` showed the generic fallback even though wallstbots' own
BOT13 verifiably DID trade today (confirmed on the live backend: BUY 5 names at 9:45 AM ET,
force-closed at 3:30pm ET with reason "daily close-out (3:30pm ET)"). Owner confirmed this
used to work correctly and is a regression, not new design.
- **Root cause:** in each `refresh_<platform>.py`'s `not _engine_window_open(...)` branch
  (market closed, no new entries), the final fallback case — when the previous decision
  isn't `"TRADE"` AND there are no stored positions, which is exactly the state right after
  close-out flattens everything — unconditionally overwrote the rationale with the generic
  hardcoded string, discarding the real trade narrative that was still sitting in
  `prev_b13_strategy`/`b13_prev_strategy` from earlier that day.
- **Fix:** added one more `elif` branch, checked before the generic fallback, that keeps
  showing today's real rationale/picks/projected-return whenever
  `prev_b13_strategy.get("day") == today` and a real rationale already exists. Only falls
  back to the generic "waiting for next session" message when BOT13 genuinely did not trade
  at all today. Applied identically (Parity Rule) to `refresh_wallstbots.py`,
  `refresh_lvl13.py` (this is the aistocks.tech engine — see Architecture note below),
  and `refresh_bitbot13.py` (crypto variable is named `b13_prev_strategy`, not
  `prev_b13_strategy`, but same logic).
- **Separately discovered and fixed in the same pass (unrelated, pre-existing): all three
  `refresh_*.py` files were truncated mid-save**, cut off inside the `news_data = {...}`
  dict literal near the end of the file — missing the `generated_at` key, the closing
  brace, the news push call, the reports push, the member-portfolio-simulation call, and
  the snapshot trigger. This is the same failure mode flagged in the truncation-guard memory
  (mid-save cutoff on `.py`/`.html` files) recurring on files the guard was supposed to
  already cover — worth a closer look at whether the guard is actually catching every save
  path, since it visibly did not catch these three. Recovered `refresh_wallstbots.py`'s tail
  from an untouched backup copy found on disk (`/tmp/wsb_check/...`, pre-dated my fix, so the
  fix was re-applied on top of it); reconstructed `refresh_lvl13.py`'s and
  `refresh_bitbot13.py`'s tails by hand using the recovered wallstbots tail as the template
  (same news/reports/portfolio-simulation/snapshot structure, just swapping the platform name
  and print-prefix strings). All three now `py_compile` clean.
- **Verified:** all three files compile with `python3 -m py_compile`; the new `elif` branch
  text is present exactly once in each file; confirmed via direct read that the branch sits
  in the correct place (before the generic fallback `else`, after the `_stored_pos`
  graceful-recovery `elif`).
- **NOT yet verified live** — this requires the owner to commit + push (see below), then
  wait for the next scheduled refresh to run, then check `wallstbots.tech/#/fund/bot13` on a
  day BOT13 trades and gets closed out.

---

**2026-06-23 — Push completed: `d112334` (BOT13 close-out mirror fix) is now on GitHub
master.** This had been blocked for most of the session by a recurring git problem on the
owner's machine, now diagnosed and permanently fixed:
- **Root cause of the original "fatal: ... is not a valid object" / "fatal: stash failed"
  error during merge:** the push script's own log file
  (`PUSH_CLOSEOUT_FIX_2026-06-23_LOG.txt`) was tracked by git. Every line the script wrote
  to its log *after* committing made the working tree dirty again with a trivial
  CRLF-only diff, right before the merge step ran. `git merge` tried to autostash that
  1-line diff and hit a missing/corrupted object in the local object database — an
  isolated, pre-existing piece of repo damage unrelated to any real commit or file.
  **Fixed permanently:** added `*_LOG.txt`, `*-log.txt`, `*-result.txt`, `*-RESULT.txt` to
  `.gitignore`; the push script now untracks any currently-tracked log files
  (`git rm -r --cached`) and does a final clean-check immediately before merging; the merge
  command now also runs with `--no-autostash` as a backstop. This class of error cannot
  recur from this script or any future one that follows the same log-file naming pattern.
- **Separate, one-time benign hiccup after that fix:** the first hardened run merged
  cleanly but then `git push` was rejected ("cannot lock ref ... is at X but expected Y")
  because an automated bot auto-refresh commit landed on GitHub in the few seconds between
  the script's fetch and its push. Not corruption — just a timing race. The script is
  designed to stop safely without force-pushing when this happens; the fix was simply to
  re-run it once more, which fetched the latest state and pushed clean.
- **Final result, confirmed from the script's own log:** Step 3 merge succeeded
  (`Merge made by the 'ort' strategy`), Step 4 push succeeded
  (`6f17411..edf3bbc master -> master`), final line `=== DONE: PASS ===`. Commit `d112334`
  plus a bundled commit cleaning up 69 stale helper-script result/log files are both now on
  `origin/master`.
- **What this means for the owner:** nothing further to do. The fix takes effect
  automatically on the next scheduled refresh for wallstbots/aistocks/bitbot13 — no manual
  deploy, no redeploy of the backend, no site visit required.

---

**2026-06-23 (earlier this session) — Real regression found and fixed: BOT13 fund page contradicted itself
post-close-out (Strategy=HOLD/0%/blank Holdings next to a positive Today's Change and a
populated Trade History).** Owner correctly rejected my first read of this as a labeling
issue — it was a real data bug. Root cause: commit `5374245` (2026-06-22) added a 3:30pm ET
/ 9pm ET force-close-out step to the three platform tracker scripts
(`refresh_wallstbots.py`, `refresh_lvl13.py`, `refresh_bitbot13.py`) but never to
`Project/scripts/refresh_portfolios.py` — the one shared script that computes the
per-member numbers the `#/fund/bot13` page actually reads. After close-out, the tracker
correctly showed the day's real (closed) gain and trade history, but `refresh_portfolios.py`
kept independently re-asking "what should BOT13 do right now" and got a fresh
HOLD/0%-with-no-positions answer that wiped Holdings, while Trade History/Today's Change
(carried from elsewhere) still showed the real trade. Fix: ported the same close-out
mirror logic into `refresh_portfolios.py` (gated on `past_close_out(cfg)` + same-day stored
strategy was TRADE + positions still held) so Holdings and Strategy now flip to
empty/HOLD together, in sync, instead of one updating and the other staying stale. Trade
History and Today's Change were already correct and are untouched. The chronological
trade-log sort (`stamp_and_log`'s `last_buy_ts`/`_not_before` clamp, added in the same prior
commit) was re-confirmed correct and did not need any change. Because `refresh_portfolios.py`
is a single file shared by wallstbots/aistocks/bitbot13 (not a per-site duplicate), this one
fix satisfies the Parity Rule automatically — no separate per-site porting needed.
**Separately discovered and fixed in the same pass (unrelated, pre-existing):** the live
copy of `refresh_portfolios.py` was truncated at line 765 mid-statement, missing its entire
`run()` entrypoint and `__main__` block — the script could not have been invoked stand-alone
or imported correctly at all regardless of the close-out bug. Restored the missing tail from
a clean GitHub clone. Verified with `py_compile` + `ast.parse` against a patched copy of the
clean clone (the working-directory file lives on a Windows-mounted drive the sandbox shell
can't reliably re-read after edits — confirmed correct via the file-editing tool's own
read-back instead). **NOW COMMITTED AND PUSHED** — see the entry at the top of this file
for the full story of the index corruption, the OneDrive/.git junction fix, and the
log-file-autostash bug that delayed this push. Final commit on `origin/master`: `edf3bbc`.


Backend redeployed and verified healthy (`wallstbots-backend-00109-7v8`); **bitbot13 full
reset is 100% COMPLETE across all 3 layers AND confirmed on GitHub** (commit `d2d35b7`).
A full claimed-vs-actual audit (repo code AND live pages, all 3 sites) ran 2026-06-22 — see
Session Log "Full audit." Everything from the last two weeks of fixes (Track Record tile,
trade ledger, 15-min refresh, Manage Subscription, free signup, timestamp fix) is confirmed
LIVE right now. **One open item, parked — NOT a simple bug:** aistocks.tech shows "$49,000" as
the "Started at" number on the bot race display (`assets/app.js` line 557). Owner clarified
2026-06-22: aistocks truly did start at $49,000, but a stock was added to the universe later,
which complicates what the "correct" displayed number should be — this is **not** a one-line
hardcode fix. Owner says: leave open for now, may require a **full reset** (hard-delete all 5
aistocks bots' history at the source — see the standing "full reset" definition) rather than a
code patch. **Do not fix this without further direction from the owner.** See
`AUDIT_PUNCHLIST_2026-06-22.md` for the full owner-facing list.

**2026-06-22 (follow-up investigation — "3 fixes I don't see working"):** Owner asked to
re-check admin referral codes, BOT13 timestamps, and the new email schedule against
HANDOFF.md, the code, and the live data. Findings: (1) **Real bug found, now FIXED.**
Correction to an earlier note in this entry: the `GY_ADMIN_TIER` fix only ever existed on
**aistocks.tech** — wallstbots.tech never had it either (both wallstbots and bitbot13 hardcoded
"INSIDER"). bitbot13.tech's `assets/app.js` was missing the admin-code-tier fix entirely: it
hardcoded "INSIDER" in the claim banner, the claim button, and the thanks page even when a
SYNDICATE-tier code (`adminm13`) was used — and wrongly showed the "Upgrade to SYNDICATE"
upsell to someone who already had it. It also had a second, separate bug: `claimAdminAccess()`
read from `admin-email`/`admin-password`/`admin-claim-msg` element IDs, but the form it actually
rendered used `adminEmail`/`adminPw`/`adminClaimMsg` — a field-ID mismatch that meant clicking
"Claim" could never read the typed email/password at all. The account itself always got the
correct tier server-side (`Backend/main.py`'s `/auth/signup-with-admin-code` resolves
`admin_tier` correctly), so no one was locked out of paid access — both were frontend-only bugs,
but real and visible ones. **Fixed 2026-06-22 on ALL THREE product sites:** copied the exact
working pattern from aistocks.tech's `assets/app.js` (the only site that had it right) into
both bitbot13.tech and wallstbots.tech — added `GY_ADMIN_TIER`, dynamic tier text in the
banner/button/thanks page, and a conditional SYNDICATE upsell/perks block. bitbot13.tech also
got the `admin-email`/`admin-password`/`admin-claim-msg` field-ID fix (it had the wrong IDs
entirely); wallstbots.tech's IDs (`adminEmail`/`adminPw`/`adminClaimMsg`) were already
internally consistent, so only its hardcoded tier strings were made dynamic. Per owner
instruction, parity-file bugs now get fixed on all three sites in the same pass rather than
fixing one and asking about the rest. Code-side verified by direct re-read of all three edited
files. **Pushed to GitHub 2026-06-22** (commit `fc30335`, merge-completed as `762c290`;
`git fetch` confirms local master == `origin/master`). Cloudflare Pages auto-deploys on push,
so wallstbots.tech and bitbot13.tech should be live with this fix within minutes of the push —
**owner should spot-check both sites' `#/get-yours` admin-code claim flow** (banner, claim
button, thanks page all say "SYNDICATE" for a syndicate code, and bitbot13's Claim button
actually creates the account) to fully close this out.

**2026-06-22 (cleanup — loose uncommitted files):** Found 16 files sitting locally,
modified/untracked but never committed: `Backend/deploy.sh`, `DEPLOY-BACKEND.bat`,
`SAFE-DEPLOY-RESULT.txt`, `deploy-backend-result.txt`, `deploy-to-cloud-run.ps1`,
`deploy-tracker-update.ps1`, `AUDIT_PUNCHLIST_2026-06-22.md`,
`Project/scripts/fix_bitbot13_source.py`, and several gcloud/Cloud Run log and PowerShell
helper files — leftovers from earlier backend-deploy work, unrelated to the admin-tier fix.
The new `fix_bitbot13_source.py` had a real syntax error (`del` used as a ternary expression,
e.g. `del x if cond else y`, which Python doesn't allow) plus a hardcoded sandbox-only file
path — both fixed (split into a proper `if/else`, path now derived from `Path(__file__)`).
**Committed + pushed** (`fc30125`) via `COMMIT-LOOSE-DEPLOY-FILES_2026-06-22.bat`. Local
master now matches `origin/master` with nothing outstanding.
(2) **Timestamps: working.** `et_now()`/`stamp_and_log()` are
used identically in all 3 refresh scripts, and wallstbots' live local data shows real ET trade
times today (`entry_time: 2026-06-22T13:43:31`, `last_refresh: 2026-06-22T18:11:48`) — no
mislabeled-UTC garbage times. (3) **Email schedule: working.** All 3 sites' GitHub Actions
workflows (`refresh-wallstbots.yml`, `refresh-bitbot13.yml`, `refresh-lvl13.yml` — the last one
drives aistocks.tech despite the old filename) have the 15-minute trading-hours cron, the
"Snapshot prior trade count" step, and the `check_bot13_traded_today.py` anti-spam gate, matching
HANDOFF.md's description exactly. **Confirmed live on GitHub Actions** (owner screenshot,
2026-06-22 5:37 PM): the aistocks workflow (`refresh-lvl13.yml`) has 110 runs total, most recent
run 20 minutes prior, both of the last two runs green/successful, ~41-43s each — actually firing
on schedule, not just correctly configured in the YAML.

---

## Overall State (plain English)

The Wall St Bots **product** is three near-identical sites: **wallstbots.tech** (sector
stocks), **aistocks.tech** (AI/quantum stocks), **bitbot13.tech** (crypto + crypto hours). It
was built by getting **one** site working, then **cloning** it. Each clone was edited
separately and features were added on top. Because the "shared" files are actually three
separate copies (see `ARCHITECTURE.md` §6), the sites drifted apart — fixes to one copy don't
reach the others, so right now **none** of the three product sites is fully working end-to-end.

**lvl13.tech is the parent-company landing page, NOT a product site.** It is excluded from
this status table and from all stabilization/parity work. 🔒 Do not modify it (CLAUDE.md
Rule 10). Its only backend dependency is a read-only cross-site Bot13 P&L box.

The goal right now is **not** new features. Get back to **one** fully working product site
(wallstbots), lock it as the reference, then bring the other two to parity — ideally
de-duplicating into shared code so this can't happen again.

---

## Per-Site Status (the 3 product sites)

Mark each row honestly. Use: ✅ works · ⚠️ partly works · ❌ broken · ❔ untested

| Capability | wallstbots | aistocks | bitbot13 |
|------------|:----------:|:--------:|:--------:|
| Homepage loads | ❔ | ❔ | ❔ |
| Live leaderboard shows data | ❔ | ❔ | ❔ |
| Signals section | ❔ | ❔ | ❔ |
| News (correct topic only) | ❔ | ❔ | ❔ |
| The Race / fund pages | ❔ | ❔ | ✅ ALL 5 bots FULL RESET 06-22 (history hard-deleted, all 3 layers complete) |
| Reports | ❔ | ❔ | ❔ |
| Signup | ❔ | ❔ | ❔ |
| Login | ❔ | ❔ | ❔ |
| Logged-in dashboard | ❔ | ❔ | ❔ |
| Get Yours / pricing | ❔ | ❔ | ❔ |
| Stripe checkout | ❔ | ❔ | ❔ |
| Stripe billing portal (Manage/Cancel) | ❔ | ❔ | ❔ |
| Referral dashboard | ❔ | ❔ | ❔ |
| Admin code → correct tier banner | ✅ | ✅ | ✅ FIXED 2026-06-22 (admin-tier hardcode resolved, parity confirmed in code) |
| Admin panel | ❔ | ❔ | ❔ |
| Chatbot (quick replies + typed input) | ❔ | ❔ | ❔ |

> Checkout is **Stripe** (`/stripe/create-checkout` + webhooks). PayPal config still exists in
> `main.py` but is legacy, not the active flow.

**Separate, read-only check for lvl13 (do not edit lvl13):**

| Capability | lvl13 (parent) |
|------------|:--------------:|
| Landing page loads | ❔ |
| Bot13 P&L box reads all 3 product sites | ❔ |
| Contact form posts | ❔ |

> **First task for the next session:** stop fixing, and fill these tables in by running
> `REGRESSION_CHECKLIST.md` against the three product sites (and the small read-only lvl13
> check). You cannot fix drift you can't see. **wallstbots.tech is the most up-to-date and is
> the reference.**

---

## 🔒 Pre-launch security (Supabase advisors)

✅ **The 3 CRITICAL issues FIXED & verified 2026-06-15** (ran in Supabase SQL Editor):

- `portfolio_comments` — RLS now ENABLED (verified `relrowsecurity = true`); public anon
  INSERT/UPDATE/DELETE/TRUNCATE revoked. Public SELECT kept (comments are meant to be readable)
  but now filtered to non-deleted rows by the existing policy.
- `support_tickets` — RLS ENABLED (verified `true`); all anon + authenticated grants revoked →
  backend (service role) only.
- `user_dashboard_summary` view — set `security_invoker = true`; anon + authenticated read revoked.

**Why safe:** the FastAPI backend uses a direct Postgres (service-role) connection that bypasses
RLS, so backend features are unaffected. Confirmed working. Fix files retained:
`Backend/RUN_FIRST_security_TEST.sql`, `Backend/security_FIX_rls.sql`.

✅ **The remaining advisor issues FIXED & verified 2026-06-15** (all 7 now resolved):

- Functions `generate_referral_code` and `update_timestamp` — pinned `SET search_path = public`
  (cleared the "Function Search Path Mutable" warnings). Verified both show `search_path=public`.
- Views `bot_latest_performance`, `promo_code_usage`, `user_referral_stats` — set
  `security_invoker = true` (same fix as `user_dashboard_summary`). `promo_code_usage` and
  `user_referral_stats` also had anon/authenticated read revoked (sensitive). `bot_latest_performance`
  left publicly readable on purpose (shown on the product sites).

**Final verification query returned 0 rows** — no public tables without RLS, no SECURITY DEFINER
views remaining. Full security advisor list cleared. (Re-check the Supabase Advisor page to see
the count at 0.)

---

## Live audit 2026-06-15 (public pages, all 3 product sites)

Audited the rendered live sites (not just code). Most of the old known-bugs list is STALE —
already fixed in current code:
- ✅ Chatbot: now a proper `<form id="chatbotForm">` with `chatbotRenderQuick()` wired up in all
  3 sites; the old undefined `handleChatbotInput` is gone. Not broken.
- ✅ `#/login` and `#/signup`: route to real standalone pages (e.g. `/login`), not the homepage.
- ✅ The Race / Signals / News / Reports / Get-Yours: render cleanly on all 3 (correct per-site
  numbers — wallstbots $55k/55, aistocks $50k/50, bitbot13 $50k/50 coins), no error banners, no NaN.
- ✅ aistocks shows TODAY's data on the rendered site (data-pipeline fix verified end-to-end).

**Real bug found + FIXED:** Signals "last run -226m ago" showed NEGATIVE minutes. Cause:
`relTime()` did `new Date(iso)` on a timezone-less UTC timestamp (e.g. "2026-06-15T20:32:15"),
which JS parses as LOCAL time → looks hours in the future. Fixed in all 3 `app.js`: append "Z"
when no tz suffix, and clamp negative to 0. (Also noted clone drift: `relTime` sat at different
line numbers across the 3 files — bodies were identical, fix applied to all.)

**Real bug found + FIXED — FREE signup was 404 (missing backend feature).** The FREE
"Get Free Signals" box called `POST /subscriptions/free-signup`, which never existed on the
backend (404 → "Something went wrong"). The free tier was simply never built (the DB already
defaults `subscription_tier='free'`). Fix: added `POST /auth/signup-free` to `main.py`
(mirrors `signup-with-admin-code`: creates a real Supabase auth user + users row at
`subscription_tier='free'`, returns a JWT, logs them in). A free account is a NORMAL account —
when they upgrade, the existing Stripe webhook flips the same row's tier; no second signup.
Frontends (all 3): the FREE box now collects email + password and calls `/auth/signup-free`,
dropping the user into their dashboard. **Needs backend redeploy to Cloud Run** (frontends
auto-deploy via Cloudflare on push).

**aistocks BOT13 end-of-day display blanked (migration side-effect, NOT a code bug) —
WATCH TOMORROW.** After close on 2026-06-15, aistocks BOT13 showed empty HOLD (positions=0,
picks=[], projected_return=0, day_pct=0) while wallstbots correctly PRESERVED its completed
trade (decision=TRADE, 5 positions, "session complete" log, day +11.5%). Investigated: the
market-closed branch in refresh_*.py preserves the day's trade ONLY if
`prev_b13_strategy.decision == "TRADE"`. The code is **byte-identical** between
refresh_wallstbots.py and refresh_lvl13.py — so it's a DATA-state difference, not logic.
Cause: today's `lvl13→aistocks` platform-key switch (+ move to API-fallback state loading)
interrupted the aistocks bucket's prior-TRADE chain, so the preserve-branch had nothing to
preserve and wiped to empty. wallstbots' chain was never disrupted. **Self-heals** once
aistocks runs a clean open-session TRADE tomorrow (it'll then store decision=TRADE and the
after-hours refresh will preserve it). ⏳ VERIFY 2026-06-16 after the open-session refresh:
aistocks BOT13 should look like wallstbots at end of day.

✅ **HARDENED 2026-06-15 (so this can never blank again).** Added a graceful fallback to the
market-closed branch in ALL 3 refresh scripts (parity): if the prior strategy chain isn't
"TRADE" but there ARE positions stored from today, preserve and re-price those (shown as a
held TRADE session) instead of wiping to empty. Positions are re-enriched with live prices
below, so they display current values. Now the end-of-day page only goes empty when there
genuinely are no positions. Needs no backend deploy (these are the GitHub-Actions refresh
scripts) — just pushed to the repo so the next cron run uses them.

**Dashboard design restored (2026-06-15).** Owner reported the members dashboard DESIGN
changed (not a code bug). Diffed wallstbots `dashboard.html` against the last June-11 version
(commit 73acf9d): the post-11 changes were mostly good (lvl13→aistocks rebrand, upgraded
referral "Invite & Earn" panel, openStripePortal fix) — KEPT those. The actual unwanted change
was **two ADDED sections: "Live Bot Session" and "Market News."** Removed both sections + their
`loadNews()`/`loadBotSession()` bootstrap calls on **all 3 dashboards** (parity). Also fixed a
wallstbots-only bug introduced after June 11: a stray duplicated/unclosed DB-latency `<div>` in
the webmaster stats panel. Done surgically on the current files (design back, good code kept) —
not a wholesale revert.

**bot-detail.html was TRUNCATED on all 3 sites — FIXED 2026-06-15.** Owner reported the
portfolio/bot-detail page stuck on "Loading…" everywhere with an EMPTY console (no JS error).
Cause: the file was cut off mid-line in the window-bindings block (`window.clo…`), so it had
no `</script>`, no closing tags, and — critically — the `document.addEventListener('DOMContentLoaded', init)`
bootstrap was missing → `init()` never ran → every section frozen. (Line counts proved it: the
last COMPLETE version was `c5ecab8` June 11 at 1416 lines; it dropped to 1386 truncated at
`dcb73fb` June 12 and stayed broken since.) Fix: restored the exact missing tail (full window
bindings + DOMContentLoaded→init + `</script></body></html>`) from the c5ecab8 version onto each
current file, preserving all newer body content (bot_fund_state reads etc.). Applied to all 3
sites (parity); verified each now has exactly one clean ending. **This is the same class of bug
as commit `ecf5f61` ("repair truncated app.js — unexpected end of input") — truncation has hit
this project repeatedly; worth a guard.** Needs deploy (Cloudflare auto on push).

**portfolio-fund.html ALSO truncated — FIXED 2026-06-15.** After bot-detail loaded, its in-page
links (fund cards → portfolio-fund.html) "didn't load" because portfolio-fund.html was truncated
the same way (cut at line 1008 mid nav-toggle comment; missing DOMContentLoaded→init bootstrap +
window bindings + closing tags). Truncation came from `c1f7daa` (June 13, the same mega-commit).
Last complete version: `c5ecab8` (June 11, 1039 lines); current was 1008. Restored the 31-line
tail onto all 3 sites (parity), preserving newer body content (d9859b8 bot_fund_state stat-card
change). **Full truncation sweep done:** scanned every member HTML across all 3 sites — only
bot-detail, dashboard (design, not truncation), and portfolio-fund were affected; index/admin/
login/leaderboard all end cleanly. **ROOT-CAUSE INVESTIGATED + GUARD ADDED (2026-06-15).** Findings: (1) NO script in the repo
rewrites these HTML files — the JSON deploy script (`deploy_to_hostgator.py`) uses binary mode
and only touches *.json; `update-frontend-api-urls.py` correctly uses encoding='utf-8' and only
touches login/signup/index. So the truncation is NOT a deploy-script bug. (2) Every truncation
cut off at a box-drawing char (`─` in the `// ── … ──` comments) leaving a `�` replacement char.
That signature = a tool/editor that re-wrote the whole file with the wrong encoding or hit an
output-length limit mid-file (consistent with an AI/editor regenerating large files; the repo
also lives under OneDrive, which can interrupt writes). Exact tool unconfirmed (owner unsure how
files are edited). **GUARD (makes cause irrelevant for prevention):** added a git pre-commit hook
`Project/scripts/pre-commit-truncation-guard.sh` that BLOCKS any commit containing an HTML file
not ending in `</html>`, installed via `INSTALL-truncation-guard-doubleclick-me.bat` (run once),
plus a standalone `CHECK-truncation-doubleclick-me.bat` to scan on demand. A truncated file can no
longer reach git/production. **Optional next:** replace the `─` box-drawing chars in comments with
plain ASCII so the specific bytes tools choke on are gone (belt-and-suspenders).

**Guard already caught one (2026-06-15):** the new checker flagged `aistocks.tech/signup.html`
as truncated (cut mid-function at line 245). It's orphaned dead code — nothing links to it
(/signup redirects to login.html#signup; real signups go via Get Yours / free-signup), and it
exists on no other site. Deleted via `FINALIZE-guard-and-cleanup-doubleclick-me.bat`. 21/22 HTML
files were clean. **Guard layers:** `SAFE-DEPLOY-doubleclick-me.bat` (runs PowerShell check before
every deploy — THE reliable layer), git pre-commit hook (installed; fires if Git-for-Windows runs
.sh hooks), `CHECK-truncation-doubleclick-me.bat` (on-demand). Checkers use PowerShell (plain
batch choked on HTML special chars — first version gave false positives, now fixed).

**BOT13 bad-data blowup (bitbot13) — FIXED 2026-06-15.** A garbage price feed gave JUP a fake
+1629.79% 24h move (entry_price 1.4e-05 vs real ~$0.40); BOT13's crypto engine had NO sanity cap,
so it deployed 100% into JUP and inflated bitbot13 BOT13 to ~$1.28M (+2460% all-time), poisoning
the leaderboard + the 06-15 snapshot + day_pct on all funds. Fix: added a **bad-data guard to BOTH
engines** in `bot13_engine.py` — reject any pick whose 1h/4h/24h (crypto) or day (equity) move
exceeds a sane cap (crypto 60%, equity 40%); bad data can never become a trade again. Data cleanup:
`Project/scripts/reset_bitbot13_bot13.py` resets BOT13 to last-good (June-11 ~$66,437), clears the
bad JUP position/strategy, and de-poisons the 06-15 snapshot + leaderboard. Run via
`FIX-bot13-baddata-doubleclick-me.bat` (deploys guard, then resets). Cloud Run redeploy needed for
the engine (the .bat handles it). ⏳ Owner to run + verify bitbot13 BOT13 shows ~$66k not $1.28M.

**aistocks header logo missing — FIXED 2026-06-15.** Header `assets/logo.svg` was blank on the
live site (loaded:false / 404) while the footer (favicon.svg) showed. Root cause: the logo.svg
file existed on local disk but was **never committed/tracked by git** (git status showed `A` =
new file on add), so Cloudflare had nothing to serve. Markup/CSS/path were all correct (identical
to working wallstbots). Fix: `git add -f` the file + push (commit 5ff8546). ⏳ Pending Cloudflare
deploy propagation — owner to Ctrl+Shift+R after ~5 min; header robot should then appear. (If
still blank after deploy completes, investigate Cloudflare SPA routing intercepting /assets/.)

**Stripe checkout "Token expired" — FIXED 2026-06-15.** Clicking Subscribe → "Redirecting to
checkout…" → dead-ended on `alert('Checkout error: Token expired')`. Cause: `startStripeCheckout()`
sent the raw JWT from localStorage without checking expiry or refreshing it; the backend rejected
the stale token. auth.js HAS a `refreshTokenIfNeeded()` but app.js never called it. Fix: added a
self-contained `ensureFreshJWT()` to all 3 product sites that decodes the JWT exp, and if expired,
mints a new access token via `/auth/refresh` using the stored refresh token; if that fails (no/dead
refresh token) it routes to /login instead of the dead-end alert. Also catch 401/"token" responses
from checkout and route to login. Applied to all 3 (parity; per-site refresh-token keys). Deploy
via SAFE-DEPLOY. ⏳ Owner to re-test: log in, click Subscribe — should reach Stripe checkout (or a
clean re-login prompt), never "Token expired".

**Get Yours Stripe panel — 2 small fixes 2026-06-15.** (1) "SECURED BY STRIPE" showed TWICE
(a static one in the panel header `.powered` + a duplicate in the dynamic button render) — removed
the dynamic duplicate; kept the header one. (2) Returning via browser-back from Stripe left the
Subscribe button stuck disabled on "Redirecting to checkout…" (bfcache restore) — added a `pageshow`
handler that re-renders the pricing panel (`updateGyPricing()`) when restored on the get-yours route,
re-enabling the button. Both applied to all 3 sites (parity). ✅ Stripe checkout itself CONFIRMED
working end-to-end (reaches live checkout.stripe.com — JBM Capital LLC, $49.99 Member Monthly).

**"Manage Subscription" button dead — FIXED 2026-06-15 (all 3 sites).** The account-drawer
"Manage Subscription →" button called `openSubModal()`, which was **referenced but never defined**
on ANY of the 3 dashboards → clicking did nothing (silent JS error). Same for `closeSubModal()`.
wallstbots was ALSO missing `openStripePortal()` entirely (clone drift — aistocks/bitbot13 had it;
corrected 2026-06-22 — commit `4eda376` confirms it was wallstbots, not aistocks as originally noted).
Fix: defined `openSubModal()` (populates plan/status/renewal from `subscription`, shows the modal
via `.open` → `display:flex`) + `closeSubModal()` on all 3; added `openStripePortal()` to wallstbots.
Now: Manage Subscription → modal → Manage Billing/Cancel → Stripe billing portal. ✅ Verified live
on all 3 sites 2026-06-22 (modal functions present and reachable on the deployed dashboards).

**Branding leftovers from lvl13→aistocks migration — FIXED 2026-06-15.** (1) aistocks
`bot-detail.html` header said "Level XIII" (the page's own SITE brand) → fixed to "AI Stocks"
(matches how wallstbots uses "Wall St. Bots"). (2) aistocks homepage hero ended "Welcome to
Level 13." → "Welcome to AI Stocks." (wallstbots says "Welcome to Wall St. Bots"). (3) og-image.svg
(social-share preview) said "LVL13.TECH / AI & Quantum Stock Tracker" on ALL 3 sites (stale) →
each now shows its own: AISTOCKS.TECH (AI & Quantum), WALLSTBOTS.TECH (Sector Stock Tracker),
BITBOT13.TECH (Crypto Trading Bot Tracker; also fixed "Sector-filtered news"→"Crypto news").
LEFT ALONE (intentional parent-brand, identical across sites): "Also from Level 13" footer label,
"platform — Level 13" tagline. (4) aistocks portfolio-fund broken header logo = the same `logo.svg`
fix already deploying. Principle applied: each section identical site-to-site, differing only by
the site's own identity.

**MEMBERS-AREA BUGS (fixing one-by-one, ONLY members pages — public pages are correct):**
- ✅ aistocks portfolio-fund.html "Started at" was hardcoded `$49,000` (lvl13's old 49-stock global
  capital — migration drift) instead of the member's `holdings.length × $1,000`. Fixed to use the
  already-computed `cap` var. wallstbots/bitbot13 already used `cap` (aistocks-only bug). Applies to
  all 5 bot views.

- ✅ Member portfolio-fund Performance chart didn't match the cards. Root cause: the chart reads
  `bot_performance_snapshots` (a SEPARATE table that lags — was stuck on 06-12) while the Current
  Value card reads live `bot_fund_state`. Two sources of truth. Frontend fix (all 3 sites): append
  the live `fundState.total_value` as the chart's final point when its date is ≥ the last snapshot
  (correct same-day, append if newer), and use `fundState.gain_loss_pct` for the return label. Chart
  now ends at the true current value. **BACKEND follow-up (deferred):** `bot_performance_snapshots`
  isn't being appended daily by refresh_portfolios.py — the gap between last snapshot and today still
  has no daily points. Fixing the snapshot-write pipeline would give a complete daily trajectory.

- ✅ JUP +1629.79% bad-data ALSO showed in the members area (BOT13 leaderboard, TOP BUYS signal,
  baselines). The earlier fix guarded `bot13_engine.py` (member BOT13 uses it via run_bot13_crypto)
  + reset the PUBLIC bucket — but `refresh_portfolios.py` computes baselines/signals/day_pct from
  raw prices directly with NO cap, so JUP's garbage prev_close still poisoned member data. Fix:
  added a bad-data guard in `refresh_portfolios.py` `fetch_prices()` — if a coin's implied day move
  > 60%, neutralize its prev_close (day move → ~0%) so junk never propagates to baselines/signals/
  scoring. Self-heals on the next refresh_portfolios cron run (recomputes per-run; no manual reset
  needed for the member side). It's a GitHub-Actions script — next cron run uses it, no Cloud Run deploy.

**Not yet tested (needs a test login):** admin panel, referral dashboard, logged-in member portfolio
data. Owner to verify dashboard + bot-detail + portfolio-fund after deploy.

---

## Known Bugs (from SITE_SPEC.md audit, 2026-05-20 — verify if still present)

### bitbot13.tech/assets/app.js
- `handleChatbotInput()` is called but never defined → chatbot text input crashes silently
- `chatbotRenderQuick()` is defined but never invoked → quick-reply buttons stay empty
- `#/login` and `#/signup` hash routes unhandled → "Log in" links fall through to homepage
- `admin.html` getToken reads only `auth_token`, missing the `bitbot13_jwt` fallback

### aistocks.tech (the migrated former lvl13 trading site)
- Its refresh script is `refresh_lvl13.py` (NOT renamed — owner confirmed this is fine). It carries the AI/quantum universe and pushes `{"platform":"lvl13"}`.
- It is **missing** the `state.json` try/except + live-API fallback (confirmed — see Backend section).
- Check `admin.html` JWT fallback chain on aistocks (VERIFY against the deployed site).

### lvl13.tech (parent site — NOT a product; do not "fix" as part of this work)
- The repo's `Frontends/lvl13.tech/` still holds stale pre-migration trading-clone files. This
  is known and tracked separately (optional `CLEANUP-lvl13-leftovers-*.bat`); it is NOT a
  product-site bug and must not be folded into stabilization work. The live lvl13 landing page
  is correct and backed up at `Backups/lvl13.tech_live_2026-06-15_1419/`.

### Backend / refresh scripts
- ✅ **FIXED 2026-06-15 — state.json corruption guard now on all 3 refreshers.** Ported
  bitbot13's try/except + live-API fallback into `refresh_wallstbots.py` and `refresh_lvl13.py`
  (all three now identical except platform string + starting-capital default). Also fixed the
  `[wallstbots]` → `[lvl13]` mislabel in `refresh_lvl13.py`. ✅ Syntax-verified 2026-06-15:
  all three compile cleanly (Python 3.14.4, via CHECK-refresh-scripts .bat).
- ✅ **FIXED 2026-06-15 — `origin_platform` DB constraint corrected.** Ran the corrective
  ALTER in Supabase; constraint now `CHECK (origin_platform IN ('aistocks','bitbot13','wallstbots','unknown'))`
  (was the stale `lvl13/bitbot13/wallstbots`). Verified via `pg_get_constraintdef`. `subscriptions`
  table was empty (0 rows) so no data relabel was needed. Backend was already correct (Stripe
  webhook writes the right platform values) — no code change required.
- **AI site refresh runs under the `lvl13` name (intentional — owner confirmed OK).** `refresh_lvl13.py` feeds the AI/quantum site (now aistocks.tech) and pushes `{"platform":"lvl13"}`. Not to be renamed.
- News scripts historically pulled broadly without strict source/keyword filters → off-topic articles slip through (verify per site).

---

## The Root Cause (do not lose sight of this)

**Cloning instead of sharing.** Three copies (one per product site) of `auth.js`, `api.js`, `app.js`, `login.html`, `dashboard.html`, `admin.html`, `bot-detail.html`, and the `refresh_*.py` scripts. Every fix has to be made three times or the sites drift. This is the thing to fix structurally — see the recovery plan below. (lvl13 is not part of this set.)

---

## Recovery Plan (the order to do things in)

1. **See the truth.** Run `REGRESSION_CHECKLIST.md` on the three product sites; fill in the table above. (Run the small lvl13 check read-only.)
2. **Pick the reference.** wallstbots.tech is currently the most complete. Confirm it is the cleanest, then declare it the reference.
3. **Get ONE site fully green.** Bring the reference site to 100% on its own checklist. Do not touch the other two yet.
4. **Lock it.** Commit. Tag it. This is the known-good baseline you can always return to.
5. **Bring the other two to parity — one at a time** (aistocks, then bitbot13). Port the reference's logic, verifying the checklist after each. Never two at once. Respect bitbot13's allowed differences (crypto class + crypto hours).
6. **De-duplicate (the real fix).** Once all three match, refactor the duplicated files into a single shared source each site imports, plus one parameterized refresh engine. After this, a fix is made once and is correct everywhere.

> Steps 1–5 stabilize. Step 6 is what stops this from ever happening again. Per the platform-health priority, step 6 is not optional — it's the point.

---

## Session Log (append newest at top)

- **2026-07-10 (MISSION AUDIT fixes):** (1) bot13_engine.mark_position bad-data guard no longer
  REWRITES recorded entry_price/shares — it clamps the bad mark to the last good price (copy-trade
  receipts are immutable). (2) Copy-trade disclosure line ("simulated fills at feed prices at decision
  time; excludes spreads/commissions/fees") added to the BOT13 fund page in all THREE product sites'
  app.js AND all three portfolio-fund.html member pages (Rule 3 parity, members included).
  (3) Verified refresh_portfolios.py inherits the 7/10 live-entry fix via its run_bot13_equity/crypto
  imports and never mutates entries in its own mark function. NUL-byte tails stripped from the three
  app.js copies (mount write artifact) — node --check passes on all three.
  REGRESSION: fund pages render on all 3 sites + member portfolio page renders; disclosure visible
  at page bottom. lvl13 untouched (Rule 10).
- **2026-07-10 (COPY-TRADE ENTRY FIX, bot13_engine.py):** BOT13 entries now fill at the
  LIVE price at decision time instead of the prior close, in BOTH build sites of the shared
  engine (run_bot13_equity ~line 693 and the crypto build ~line 899). Owner's mission ruling:
  members must be able to copy any trade in real time at its recorded price — the prior close
  is the SIGNAL baseline only, never a fill. Affects the platform BOT13 funds on all three
  product sites (wallstbots/aistocks/bitbot13) via the shared import; member portfolios were
  already fixed 2026-07-07 (real entry at real price). No other logic touched (Rule 1).
  UNTESTED until the next live session: verify each site's BOT13 entry_price equals the price
  at decision time, not yesterday's close (REGRESSION: BOT13 fund card + holdings on all 3
  sites; member portfolios unaffected). lvl13 untouched (Rule 10). Same fix + data void done
  on bot13.tech the same day.
- **2026-07-06 pm (MEMBERS P1 FIXED, commit `1adaab9`):** the three
  carry-forward guards in refresh_portfolios.py (bot13/oracle/wizard) no longer
  clamp to the platform-scaled member_value — corruption is detected vs the
  fund's OWN prior day-open and clamped to the member's own prior value. No
  platform-scaled fallback remains in the member carry-forward path. With the
  earlier readback fix (e33af74) and the audit's member assertions, the member
  section's known integrity issues are all addressed. Verify: owner refresh +
  RUN-AUDIT.bat (member section must reconcile with zero failures).

- **2026-07-06 pm (DE-DUP increment 3 — COMPLETE, commit `063ff96`):**
  oracle/wizard totals (residual cash + compounding) and BOT13 flat-day ledger
  banking extracted to `bot13_engine.hold_fund_totals` / `bot13_bank_flat_day`.
  With increments 1-2, ALL displayed-number math (position marking, day
  reference, fund day fields, hold-fund totals, ledger banking) lives once in
  bot13_engine.py — ~550 duplicated lines deleted, gates verified zero leftover
  copies. Engines keep only decision/session flow. Remaining SEPARATE item:
  refresh_portfolios.py P1 carry-forward guards (a behavior fix, not a clone
  of these blocks — needs its own owner-approved change).

- **2026-07-06 pm (DE-DUP increment 2, commit `ab57ff1`):** the fund-level
  Today's Change math (day_open from prior snapshot / day_pnl / day_pct) — NINE
  per-engine copies across oracle/wizard/equalizer-titan × 3 engines — now
  lives once as `bot13_engine.fund_day_fields`; all nine sites delegate. Gates
  verified zero leftover copies. Remaining per-engine (identical today, next
  extraction candidates): oracle/wizard total/cash residual lines, bot13 value
  blocks; plus refresh_portfolios (member engine — P1, own change).

- **2026-07-06 pm (DE-DUP increment 1, commit `ef786ba` — owner-approved, NO new
  features, no page changes).** The position mark-to-market math (incl.
  bad-entry guard + opened-today baseline), the one-clock day-reference
  resolver, and the day-boundary payload now live ONCE in `bot13_engine.py`;
  all 3 engines delegate (net −109 lines). The three enrich_position copies had
  ALREADY drifted (bitbot13 lacked current_price, preserved different fields) —
  that drift class is now structurally impossible for this math. Equity vs
  crypto output shapes reproduced exactly via a crypto flag.
  **Still per-engine (next increment, same mechanical extraction):** the
  fund-level value blocks (bot13/oracle/wizard/equalizer/titan totals) —
  currently identical after this week's parity fixes — and the member engine
  (refresh_portfolios P1 guards). Owner verifying via manual refresh + audit.

- **2026-07-06 (ONE CLOCK fix, commit `dd9c200` — audit run + diagnosis + owner-
  approved fix, no resets, no box-formula changes).** Full audit
  (`AUDIT_RESULT_2026-07-06.txt`): wallstbots + aistocks ALL CLEAN; 6 failures,
  all explained: (1) bitbot13's 4 hold funds — Today's Change box (vs yesterday's
  fund snapshot) and Holdings TODAY column (vs feed prev_close) measured from two
  different clocks; crypto has no official close, so they could never reconcile.
  Fix: engines store `day_boundary` prices (the prices each day's snapshot was
  written from); next day's display math uses them — one clock, all 3 engines in
  parity, signals untouched. (2) 2 member "DAY-1" failures were audit false
  positives (1% detection window mislabeled day-2 funds) — detection now exact,
  and the Holdings-TODAY check accepts the rotation-day identity. Also: BOT13
  intraday cash = total − pos_val so total==cash+pos_val holds mid-session.
  **Timing:** the first refresh after deploy still shows bitbot13's old
  box-vs-column gap (no boundary stored yet); it stores today's boundary and the
  gap closes at the NEXT day roll. Cash + audit fixes show immediately.
  Commit-message tail mangled by a cmd %% expansion — cosmetic; code verified on
  GitHub. Long-term direction (proposed, not started): ledger-as-source-of-truth
  + one shared calc module (Recovery Order step 7).

- **2026-07-06 early (REFERRAL FLOW end-to-end: commits `998e30f` + `92de513`
  pushed and verified live).** Two independent breaks fixed:
  (1) Router: `#/get-yours?ref=CODE` fell through to the homepage because
  route() matched the hash including the query — invitees never saw the signup
  page or their code. Fixed (one line, all 3 sites).
  (2) Confirm-email dead end: no signup path passed redirect_to to Supabase,
  so the confirm link fell back to the project's stale Site URL. Backend now
  sends per-platform redirect to login.html?confirmed=1; login.html (×3)
  handles the return (auto-session or "confirmed" banner); login error now
  says "Email not confirmed" when true.
  - **OWNER ACTION REQUIRED (Supabase dashboard):** Authentication → URL
    Configuration → Site URL = https://wallstbots.tech; add all three
    https://<site>/login.html to Redirect URLs. Until then the confirm link
    still uses the old Site URL.
  - **Flagged, not fixed:** invite emails hardcode wallstbots.tech links for
    all platforms; FREE signups don't record the ref code (referrer credit
    only fires on paid checkout via Stripe webhook +$35) — owner decision.
  - **Follow-up fix (commit `816261c`, verified live):** email click-tracking
    strips #fragments, so even with the router fixed, emailed links dropped
    invitees on the bare homepage. Invite emails now link `/?ref=CODE` (query
    form, survives any redirect); route() on all 3 sites sends `/?ref=` to
    Get Yours. Old emails still carry fragment links — send fresh invites.
    Browser caveat: app.js caches 4h, so recently-visited browsers may need
    a hard refresh (Ctrl+F5); new visitors unaffected.

- **2026-07-05 late (LEDGER IS THE ACCOUNT: commit `5ee9727` pushed — two
  accounting bugs fixed in all 3 engines + audit coverage added).**
  - Bug 1: BOT13 flat-day banking kept the previous run's price mark while the
    trade ledger realized at the current run's price (live: box +$1,406.40 vs
    Trade History +$1,528.68 on bitbot13). Now: flat balance = day_open + sum of
    today's SELL realized — same numbers Trade History shows. Closed Holdings
    rows also pinned to their SELL price (frozen receipt).
  - Bug 2: Oracle/Wizard seed/rotation deleted the undeployed rounding remainder
    (live: bitbot13 Wizard $13 short → Holdings P&L ≠ Total P&L box; this is the
    owner's reported "-26 carryover" class). Now: remainder stays as cash;
    rotations record strategy.deployed_capital; capped one-time restore recovers
    already-lost remainders on next refresh.
  - audit_integrity.py gained LEDGER==ACCOUNT and NO VANISHED CASH assertions —
    neither bug class can pass silently again. Race section / fund cards / bot
    pages reconcile automatically once the next engine run writes.
  - **Verify after next refresh:** bitbot13 BOT13 total should read $51,528.68
    (= $50,000 + $1,528.68 ledger) and Wizard's cash $13. If no engine run
    happens before midnight ET, 7/5's snapshot keeps the $122 understatement in
    history — run one manual refresh before midnight to correct it.
  - **INCIDENT, resolved:** the local `.git` folder was DELETED mid-session
    (~23:02), most likely by the desktop-session file-sync layer (same layer
    showed truncated file mirrors all night). Rebuilt from GitHub with zero
    working-file changes (RUN-GIT-RECOVER.bat, backup in
    `_recover_backup_2026-07-05/`). Nothing lost. Keep running the truncation
    guard + compile gate before every commit (tonight's scripts all do).
  - **Still pending (next change, owner-approved scope):** refresh_portfolios.py
    member-side — P1 carry-forward guards (handoff §5) + same two bug classes
    on the member path.

- **2026-07-05 evening (DEPLOY UNBLOCKED: commit `e33af74` pushed + live on Cloud
  Run — the portfolio-fund-state readback fix from HANDOFF_2026-07-05.md §2 is
  now deployed).** Revision `wallstbots-backend-00130-dg2`, serving 100% traffic,
  verified responding at `/public/tracker/state?platform=wallstbots`.
  - The old deploy `.bat` hang (handoff §1) was bypassed with a redesigned script,
    `RUN-DEPLOY-e33af74.bat`: no commit step (commit already existed), sets
    `GIT_TERMINAL_PROMPT=0` + `GCM_INTERACTIVE=never` so git fails loudly instead
    of waiting silently for hidden input, logs every step to
    `RUN-DEPLOY-e33af74_LOG.txt`, and exits with no interactive pause. Ran clean
    end-to-end on the first attempt: fetch → ahead/behind safety check → push →
    .env load → docker build/tag/push → gcloud run deploy. Use this pattern for
    all future deploy scripts.
  - Diagnostics captured (log Step 0): `commit.gpgsign` is NOT set;
    `credential.helper = manager` (Git Credential Manager). So the old hang was
    most likely GCM opening an interactive prompt/window from inside the
    double-clicked console, not GPG. Root cause not conclusively proven — the
    new script pattern removes the exposure either way.
  - **Known-good now:** backend live with the readback fix (all 3 product sites,
    one shared backend); git origin/master == local master (`e33af74`).
  - **Still UNTESTED (needs next `refresh_portfolios.py` cycle):** member
    Oracle/Wizard "Today's Change" actually moving again (e.g. bitbot13 TopCryp)
    instead of $0.00 every run. Verify after next refresh; the new
    `audit_integrity.py` member day-1 assertion also only proves itself then.
  - Working tree still has unrelated uncommitted items: modified
    PROJECT_STATUS.md (this entry), untracked PRE_LAUNCH_ANALYSIS_2026-07-05.md,
    RUNBOOK_MANUAL_DEPLOY_2026-07-05.md, `Invite`, `Send`. Owner to commit/push
    when ready.

- **2026-07-05 (PERMANENT FIX: stale duplicated "My Account" drawer removed from
  bot-detail.html + portfolio-fund.html, all 3 sites -- 6 files). Built +
  verified, staged.** Deploy: `DEPLOY-account-drawer-dedup_2026-07-05.bat`.
  - Owner reported bitbot13.tech's bot-detail page showing an old, much simpler
    "My Account" panel (just a referral code + copy button, no Invite & Earn, no
    admin codes, no email prefs) -- looked like a regression / an old file
    getting redeployed. Investigation found the real cause: `bot-detail.html`
    and `portfolio-fund.html` each carry their OWN separate, hand-duplicated
    copy of the account drawer, independent from `dashboard.html`'s real,
    current implementation -- and this is true on **all 3 product sites**, not
    just bitbot13 (owner had only tested the dashboard page on wallstbots/
    aistocks, where the real drawer lives). Every fix made to the account
    drawer today (JWT refresh, admin invite) only ever touched `dashboard.html`;
    these two other page types kept the pre-rebuild stub and always will,
    every time, until the duplication itself is removed.
  - **Permanent fix (not a resync -- structural):** `leaderboard.html` already
    had the correct pattern on all 3 sites -- its "My Account" button is just
    `<a href="dashboard.html">`, no duplicated drawer at all. Applied the same
    pattern to `bot-detail.html` (full removal: button is now a link, entire
    stale drawer/password-modal markup + its JS functions deleted) on all 3
    sites. For `portfolio-fund.html`, kept the drawer shell (it also houses
    genuinely page-specific Portfolio Settings -- privacy/leaderboard/share
    toggles -- which can't redirect anywhere) but stripped the duplicated
    account-only sections (Profile/Referral/Reset-Password) down to a single
    "Manage Account & Referrals →" link to `dashboard.html`, on all 3 sites.
  - Verified safe: every `document.getElementById('drawerXxx')` call left
    behind in surrounding code (population functions like `renderProfile()`,
    `loadReferralCode()`) is either null-checked (`if (el) ...`) or wrapped in a
    try/catch at the call site, confirmed identical across all 3 sites -- so
    removing the DOM elements causes zero runtime errors, just harmless no-op
    API calls (flagged as a minor follow-up cleanup, not urgent).
  - Result: there is now exactly ONE real account drawer per site
    (`dashboard.html`), and zero duplicated copies anywhere -- this class of
    bug (a fix landing on one page but not others) cannot recur for the
    account UI specifically.
  - **Not yet done, related, lower priority:** `wallstbots.tech/portfolio-fund.html`
    has a leftover `alt="AI Stocks"` on its logo (clone artifact, cosmetic,
    unrelated to this fix -- flagged, not touched, one concern per change).

- **2026-07-05 (RESEND_API_KEY restored -- fixes admin/personal invite emails +
  support-ticket confirmations). Built + verified, staged.** Deploy:
  `DEPLOY-backend-resend-env-fix_2026-07-05.bat` (git only) THEN
  `DEPLOY-BACKEND.bat` (Cloud Run -- required).
  - Same root cause pattern as the Stripe fix above: `RESEND_API_KEY` was
    missing from both `Backend/.env` and `DEPLOY-BACKEND.bat`'s
    `--set-env-vars` list, so `_send_resend_email()` always returned `False`
    silently -- every email the backend sends (admin-code invites, personal
    referral invites, support-ticket confirmations) failed with
    "Failed to send invite email. Please try again."
  - The pre-existing `wallstbots-backend` Resend key (490 total uses, active
    ~19h ago -- something else, likely the GitHub Actions email pipeline, uses
    it independently) could not be recovered: Resend never re-displays a key's
    value after creation. Owner created a fresh key scoped for this purpose
    and supplied it directly.
  - Fix: added `RESEND_API_KEY` to `Backend/.env` (gitignored, never
    committed -- confirmed via `.gitignore`) and wired it into
    `DEPLOY-BACKEND.bat`'s env forwarding + `--set-env-vars` line, following
    the same dated/logged/git-committed-wrapper discipline established for the
    Stripe fix (no more silent hand-edits to the persistent deploy script).
  - **Still untested:** owner needs to run `DEPLOY-backend-resend-env-fix_2026-07-05.bat`
    THEN `DEPLOY-BACKEND.bat`, then test sending both a personal referral
    invite and an admin-code (admin13/adminm13) invite on all 3 sites and
    confirm the emails actually arrive.

- **2026-07-05 (CRITICAL: Stripe checkout was silently broken on live backend --
  DEPLOY-BACKEND.bat fixed, dead PayPal vars removed). Built + verified, staged.**
  Deploy: `DEPLOY-backend-stripe-env-fix_2026-07-05.bat` (git only) THEN
  `DEPLOY-BACKEND.bat` (Cloud Run -- required).
  - Found while investigating the admin-invite email failure (owner asked for a
    full code pass instead of a narrow patch): `DEPLOY-BACKEND.bat`'s
    `gcloud run deploy --set-env-vars=...` REPLACES the entire Cloud Run env-var
    set on every deploy (does not merge with the previous revision). Its list
    was missing `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` -- both actively
    used by `/stripe/create-checkout` and `/stripe/webhook` in `main.py` -- while
    carrying `PAYPAL_CLIENT_ID`/`PAYPAL_CLIENT_SECRET`/`PAYPAL_MODE`, which are
    referenced NOWHERE in `main.py` (confirmed via full-file search) and aren't
    even present in `Backend/.env`.
  - **Owner confirmed Stripe is the only checkout option.** Net effect: every
    deploy via this script has been silently wiping the live Stripe keys (or
    never setting them), so `/stripe/create-checkout` has been hard-failing with
    `500 "Stripe not configured"` for every real customer trying to check out --
    not a one-off bug, a standing checkout outage.
  - Fix: `DEPLOY-BACKEND.bat` now forwards `STRIPE_SECRET_KEY` +
    `STRIPE_WEBHOOK_SECRET` (real values already in `Backend/.env`) and no
    longer references `PAYPAL_*` anywhere -- dead code removed, not left as
    silent clutter.
  - **Also still open (separate, needs owner input):** `RESEND_API_KEY` is
    missing the same way (env var never forwarded, AND the real key value isn't
    anywhere in this repo) -- this is the direct cause of "Failed to send invite
    email" on both the admin-code and personal-referral invite paths, and also
    affects support-ticket confirmation emails. Cannot fix until the owner
    supplies the real Resend API key. `POLYGON_API_KEY` has the same gap but
    degrades gracefully (falls back to manual ticker entry), lower priority.
  - **Process correction (owner called this out directly):** the previous fix
    in this session hand-edited `DEPLOY-BACKEND.bat` in place with no git commit
    and no log, then told the owner to just re-run it -- this exact pattern (a
    persistent, reused deploy script mutated silently) is how the Stripe-key gap
    survived undetected through multiple prior deploys, and is called out as a
    recurring cause of regressions blocking launch (see
    [[feedback_never_hand_edit_persistent_deploy_script]] in memory). Going
    forward: any change to a persistent/reusable script ships as its own new
    dated, logged, git-committed wrapper script, same discipline as the
    one-off frontend deploy scripts already use.
  - **Still untested:** owner needs to run `DEPLOY-backend-stripe-env-fix_2026-07-05.bat`
    (commits this fix to git) THEN `DEPLOY-BACKEND.bat` (actually pushes to Cloud
    Run) THEN test a real Stripe checkout end-to-end.

- **2026-07-05 (Admin-code invite "Admin access required" bug fixed -- backend
  only, all 3 product sites since it's one shared endpoint). Built + verified,
  staged.** Deploy: `DEPLOY-admin-invite-role-fix_2026-07-05.bat` (git only) THEN
  `DEPLOY-BACKEND.bat` (Cloud Run -- required, git push alone does not update the
  live backend).
  - Owner reported: sending the adminm13 (Syndicate) comp-code invite from My
    Account always failed with "Admin access required," even on the real
    webmaster account.
  - Root cause (2 stacked bugs in `POST /admin/send-invite`, `Backend/main.py`):
    (1) used `Depends(get_current_user)` -- the lightweight auth dependency that
    only returns `{user_id, email}`, never a `role` -- so `current_user.get("role")`
    was always `None` and the check failed for every account, no exceptions.
    (2) even with a role present, the check was `role in ("admin","webmaster")`,
    but "webmaster" is a `subscription_tier` in this app, not a `role` value (see
    `require_webmaster` and dashboard.html's `isWM` check) -- so it would still
    have failed for a real webmaster account.
  - Fix: switched to `Depends(get_current_user_with_role)` (does the DB lookup)
    and now allows `role=="admin"` OR `subscription_tier` containing "webmaster",
    matching the exact logic dashboard.html already uses to decide whether to
    show the admin-code dropdown at all.
  - Also fixed in the same pass: `DEPLOY-BACKEND.bat` was still `cd`-ing into the
    OneDrive-path copy of this repo (the copy we've been told never to use --
    see [[feedback_never_use_onedrive_folder]]). Changed to a relative `cd` off
    its own location so it always builds from wherever this repo actually lives.
  - **Still untested:** owner needs to run `DEPLOY-BACKEND.bat` after the git push
    to actually push this live to Cloud Run, then re-test sending an adminm13/
    admin13 invite from My Account.

- **2026-07-05 (Invite-by-email "Token expired" bug fixed -- all 3 product sites,
  frontend only). Built + verified, staged.** Deploy:
  `DEPLOY-invite-token-refresh-fix_2026-07-05.bat`.
  - Owner reported My Account -> Invite & Earn "Send" showing "Token expired" and no
    invite email arriving. Root cause: `sendInviteEmail()` in `dashboard.html` read the
    JWT straight out of `localStorage` and never refreshed it first, unlike every other
    authenticated call on the page (which goes through `api.js`'s `request()`, which
    always calls `auth.refreshTokenIfNeeded()` first). Supabase access tokens expire
    after ~1hr, so any account session left open longer than that hit a 401 before the
    invite endpoint was ever reached -- nothing was sent, and it looked intermittent.
    Confirmed a real bug, not intended behavior; token expiry itself is untouched.
  - Fix: `sendInviteEmail()` now calls `auth.refreshTokenIfNeeded()` first and reads the
    fresh token via `auth.getToken()` (falling back to the old localStorage keys),
    matching `api.js`'s pattern. On refresh failure it shows "session expired, please
    log in again" instead of the raw backend error.
  - Parity: identical bug in all 3 clones (per-site JWT key names differ only); fixed in
    all 3 in the same change. `admin.html` has no separate copy -- admin-code invites
    route through the same `sendInviteEmail()`, already covered. `lvl13.tech`: not
    touched (no invite feature, not in this parity set).
  - **Process note:** this fix was first (mistakenly) written to the OneDrive-path copy
    of this repo (`C:\Users\...\OneDrive\...\WallStBots`), which is NOT the live repo --
    confirmed with the owner that `C:\Claude\Websites\WallStBots` is the one that pushes
    to GitHub/Cloudflare. The OneDrive copy is out of sync (missing today's day-1-
    integrity fix below) and should not be edited or deployed from going forward -- it's
    also the source of a past truncation issue. Re-applied correctly here.
  - **Still untested:** live click-through on all 3 sites after deploy -- owner should
    send one real test invite per site and confirm the email arrives.

- **2026-07-05 (Next-session start — nothing trades on creation/reset day). Built + verified,
  staged.** Deploy: `DEPLOY-next-session-start_2026-07-05.bat`.
  - Rule refined (CLAUDE.md Rule 0): a fund/portfolio holds starting capital flat on its
    creation/reset day and takes its first REAL entries at the NEXT trading session.
  - Public engines (parity): Oracle/Wizard/Equalizer/Titan now gated to `today>inception`
    (BOT13 already was) — a reset lands everything flat that day, real entries next open.
  - Member: created-today portfolios get a PENDING state at cost (not blank) + first-trading-day
    holdings measure Today's Change from real entries. New shared `next_trading_day()` (crypto=next
    day; equity skips weekends+holidays). Portfolio page (3 sites) shows a "Trading begins <day>"
    banner using the real start date. All compile; next_trading_day logic unit-tested; parity ok.

- **2026-07-05 (DATA-INTEGRITY / DAY-1 RULE — Rule 0 established + fixes). Built + verified,
  staged.** Deploy: `DEPLOY-day1-integrity_2026-07-05.bat`.
  - Mission recorded as **CLAUDE.md Rule 0**: Day 1 = day of reset/creation; starting capital =
    N×$1,000; no inherited/scaled/fictitious numbers; everything verifiable from real day-1 entries.
  - Midday bitbot13 audit: fund numbers correct (BOT13 +$1,227.75 real), but the **per-holding
    "Today's Change"** used yesterday's close as the baseline for a lot bought TODAY (NOT bought on
    a dip → showed −$2,097 vs +$1,227). Fixed in `enrich_position` (3 engines, parity): a lot whose
    entry_time is today baselines off its **entry price**, not prior close.
  - **CRITICAL member bug fixed:** member value was `original_cost × platform_total/platform_sc` —
    a portfolio created on day 30 inherited 30 days of platform gains, and a reset would crater
    members. Rewrote `refresh_portfolios.py` so each member fund is its **own** simulation valued
    from its **own live positions**, seeded at cost on the portfolio's creation day (day 1 opens at
    cost). Member BOT13 Trade History now = the member's own trades. Held lots re-marked to live
    prices each run. Value logic unit-tested (day-1 new portfolio = 0%, day-30 create = 0%, held
    day-2, cash day, intraday re-run all correct).
  - Audit updated: dropped obsolete member==platform-scaled check; now verifies member independence.
  - Files: 3 engines, refresh_portfolios.py, audit_integrity.py, CLAUDE.md. All compile; parity ok.

- **2026-07-04 (Marketing copy rewrite — all 3 product sites). Built + verified, staged.**
  Deploy: `DEPLOY-copy-rewrite_2026-07-04.bat` (frontend only; Cloudflare Pages).
  - Home hero sells BOT13 as "the one to watch" — honest, no fabricated numbers ("results
    speak for themselves; watch them live"). How It Works expanded into a full sales page:
    intro pitch, Meet-BOT13 spotlight, edge explainer, "Why most traders lose", "Nothing to
    hide" transparency, a vs-typical-alerts-group comparison, and a run-it-on-YOUR-picks block.
  - Get Yours restructured: paid tiers first, FREE account moved to the bottom; tier bullets
    benefit-first; "BOT13 won it" claim replaced with method framing. All report wording
    updated weekly/Sunday → downloadable MONTHLY statements. aistocks: all "Claude" removed.
  - Verified: node --check on all 3 app.js; shared blocks byte-identical (only per-site asset
    words + REPORT_BRAND differ); zero Claude refs; free below paid on all 3.

- **2026-07-04 (NEW FEATURE: monthly bank-statement Reports — public + member).
  Built + verified, staged.** Deploy: `DEPLOY-reports-feature_2026-07-04.bat`.
  - Durable archive: new `daily_fund_archive` table (auto-created; schema also in
    `Backend/reports_archive_migration.sql`). Backend archives one row per fund per day
    from data the engines ALREADY push — ZERO engine changes. Hooks run on their own DB
    connection AFTER the live push commits (`_archive_state_push` in `tracker_push`;
    `_archive_member_states` in `upsert_portfolio_bot_state`), so a report hiccup can
    never touch trading data. RESET-AWARE: the archive only holds data on/after each
    fund's inception (reset) date — a reset sets inception=today, and the next push prunes
    any pre-inception rows and refuses to backfill before it, so history self-heals to
    start at the reset date (a reset was run today → reports start empty, fill from today).
  - Endpoints (backend computes every number): `/public/reports/available`,
    `/public/reports/monthly` (public, per site) and `/reports/member/available`,
    `/reports/member/monthly` (authed, `get_current_user`). Monthly P&L per fund =
    end-value − prior-month-end (or starting capital / first observed value at launch).
  - Frontend (parity, 3 sites): repurposed the `#/reports` + `#/report/<month>` routes
    (were the old weekly reports) into a monthly Reports page; bank-statement PDF built
    in-browser via jsPDF (lazy-loaded from cdnjs). Member dashboard: a "Reports" button +
    modal + combined-statement PDF (all portfolios + BOT13 daily trades + each bot's
    monthly P&L + weekly/monthly picks). Per-site only differs by REPORT_PLATFORM/BRAND.
  - Verified: main.py compiles; archive + monthly-aggregation logic unit-tested offline
    (P&L, BOT13 daily/trade-count, baseline flag, pick history); all app.js + dashboard
    inline JS pass `node --check`; reports blocks byte-identical across the 3 sites.
  - Deploys via one push (Backend/** → Cloud Run Action; frontends → Cloudflare Pages).

- **2026-07-04 (BOT13 authoritative trade ledger — replaces snapshot-diff inference).
  Built + verified, staged.** Deploy: `DEPLOY-bot13-authoritative-ledger_2026-07-04.bat`.
  - Problem: BOT13's Trade History was never recorded at execution time; the engine inferred
    buys/sells by diffing this run's holdings vs last run's. That silently lost/duplicated trades
    on missed runs, day-rolls, and same-coin re-entries (why July 4's real trades never showed).
  - Fix: new SHARED `reconcile_bot13_log()` in `bot13_engine.py` writes a BUY on every open and a
    SELL (with realized P&L) on every close, and explicitly closes any prior-day book at the day
    roll so nothing carries across midnight and no trading day is blank; log stays TODAY-ONLY.
    Wired into all 3 engines at the `if fid=="bot13"` block (parity byte-identical; only the
    EQUITY_CFG/CRYPTO_CFG session close differs). Oracle/Wizard/Equalizer/Titan untouched.
  - Audit tightened: an unpaired SELL is now a hard FAIL on every site, and bitbot13 FAILs if
    BOT13 is ever caught holding a position dated before today. Live audit = PASS (6 expected
    fresh-baseline warnings only). Known-good after the next crypto session logs a clean round-trip.
  - Files: `bot13_engine.py`, `refresh_wallstbots.py`, `refresh_aistocks.py`, `refresh_bitbot13.py`,
    `audit_integrity.py`. Compile + parity + NUL checks pass. Not yet pushed (run the .bat).

- **2026-07-02 (Holdings ALWAYS sum to the Total P&L box — oracle/wizard Total P&L = sum of
  current holdings vs their REAL cost basis; all 3 engines + member + frontends, parity).
  Built + verified, NOT YET PUSHED.** Deploy: `DEPLOY-holdings-sum-to-total-pnl_2026-07-02.bat`.
  - Owner's model (final): Oracle buys once/week, Wizard once/month, then HOLD. Each period they
    redeploy the carried-forward balance (last period's ending value, NOT $50k). Entry = the real
    price the holding was bought at; Price = current; Total P&L = value − real cost. Fund Total P&L
    box = SUM of current holdings, measured vs their cost basis (this period's deploy), so Holdings
    ALWAYS sum to the box. Compounding shows in Current Value carrying forward.
  - Engine (oracle/wizard, 3 sites): `pnl = pos_val − Σ(real cost_basis)`, `pnl_pct = pnl/Σcost`.
    Equalizer/Titan already summed (Σcost==sc); bot13 unchanged (intraday/cash). Also removed the
    inception entry_price rebase (keeps real day-1 entries correct).
  - Frontend (app.js + portfolio-fund.html, 3 sites): header shows "Cost basis" (= Current − Total
    P&L) so the three boxes reconcile; dropped stale "since inception / all-time" labels. Holdings
    table columns already match: Units, Entry, Price, Value, Today%, Total$, Total%.
  - Member (refresh_portfolios.py): Total P&L measured vs cost basis (cost = tracker total − pnl,
    scaled), entry_cost = member cost, so member Holdings sum to member Total P&L; gain_loss_pct ==
    public pnl_pct preserved.
  - audit_integrity.py: model-aware — for hold funds pnl = pos_val − Σcost and Holdings P&L MUST sum
    to the Total P&L box (proven to FAIL a mismatch). NOTE: reverted the earlier "pin cost basis to
    sc" approach (it faked entry prices — owner wants REAL entry prices).
  - KNOWN-GOOD after push+refresh: every fund page reconciles (Holdings → Total P&L) at real prices.
    Until pushed: engines apply next refresh (bitbot13 ~15min; equity oracle/wizard next market open
    — they already reconcile since Σcost≈sc). Audit will flag bitbot13 oracle/wizard only in the gap
    between deploy and the next crypto refresh. No reset (owner declined).
  - Editing note: Edit tool injected NUL bytes into audit_integrity.py (stripped + recompiled);
    prefer bash heredoc/python for big files.

  (Superseded earlier same-day entry: "pin oracle/wizard cost basis to starting capital" via
  DEPLOY-seedday-costbasis-recon — that scaled entry prices and was reverted per owner.)
  - Owner report: bitbot13 Wizard showed Total P&L ~$0 but the Holdings P&L rows summed to
    ~-$5.77. Diagnosis: NOT a bug — the compounding funds redeploy the full balance at each
    rebalance (Wizard monthly, Oracle weekly), which reset each holding's cost basis and hid the
    accumulated gain as invisible "locked realized." Holdings measured gain since last rebalance;
    Total P&L measured since inception; they differed by that locked amount.
  - Owner's model: one account that compounds forever, cost basis = original capital, every page
    number matches the live mark, NO extra "banked" line. Implemented `_pin_cost_basis_to_sc()`
    in all 3 engines: after each refresh, oracle+wizard holdings' TOTAL cost basis is pinned to the
    fund's ORIGINAL starting capital (Σcost==sc). Fund still compounds via shares; only cost basis
    is measured vs original capital, so Holdings P&L ALWAYS sums to Total P&L (total−sc). Self-heals
    live data on next refresh. equalizer/titan already reconciled (untouched). Member parity:
    `_pin_member_cost_basis()` in refresh_portfolios oracle/wizard.
  - Also removed the inception-day entry_price rebase (broke day-1 cost basis) in all 3 engines.
  - audit_integrity.py: NEW aggregate reconciliation — no-negative-cash, SEED-DAY Σcost+cash==sc,
    holdings-P&L-sums-to-Total; locked realized surfaced as INFO. Proven to FAIL a corrupted seed
    and PASS legit compounding. Daily 11am scheduled audit set up.
  - Proven on live bitbot13: oracle holdings 70.54→18.15 (==fund 18.16), wizard 17.79→−0.03
    (==fund −0.02), Σcost→50000. Live audit PASSES (7 cosmetic crypto-rounding warns, 0 fails).
  - KNOWN-GOOD after push+next refresh: all 5 funds × 3 sites reconcile holdings→Total at live
    price. UNTESTED until pushed: the engines apply on the next refresh (bitbot13 ~15min; equity at
    next market open — equity already reconciled). No reset (owner declined).
  - Side note: when a fund is up big, per-position Entry shows the effective cost-since-inception
    (below live price) — matches the "one compounding account" model.

- **2026-06-23 (Webmaster referral/admin-code selector — all 3 product sites, parity
  verified).** Owner's request: webmaster account could only send the personal 50%-off
  referral code; needed to also send the two admin comp codes (`admin13` = Insider free-
  lifetime, `adminm13` = Syndicate free-lifetime) from the same "My Account" drawer, with
  Copy Code / Copy Link / Send-by-email all following whichever code is selected.
  **What changed (frontend only — `dashboard.html` on all 3 product sites):** added a
  webmaster-only `<select id="wmCodeSelector">` dropdown (Personal / admin13 / adminm13) in
  the Invite & Earn section, gated behind the existing `isWM` check (same flag that already
  shows the Command Center nav link — no new gating logic invented). Selecting a code swaps
  the displayed code, the invite link's `ref=` parameter, and the "How it works" blurb via a
  new `onWmCodeChange()` function. `sendInviteEmail()` now branches: personal code still
  posts to `/account/invite` exactly as before (zero behavior change for regular members);
  admin13/adminm13 now post to the pre-existing, webmaster-only `/admin/send-invite` endpoint
  (`Backend/main.py`, already built and already role-gated — **no backend changes needed**),
  which sends the existing "free lifetime account" branded email template.
  **Parity:** wallstbots.tech was the reference build; identical markup + JS ported to
  aistocks.tech and bitbot13.tech in the same session. Verified by grepping all 3 files for
  every new hook (`wmCodeSelectorWrap`, `onWmCodeChange`, `referralHowItWorks`,
  `_personalRefCode`/`_personalRefLink`) — identical counts and call sites in all three.
  **Not yet done:** live click-through test in a browser (sandbox/bash tool was unavailable
  this session — verification was code-level: structure, naming, and gating logic cross-
  checked across all 3 files, not run in a live page). Owner should click-test the dropdown
  on wallstbots.tech first after deploy, confirm a non-webmaster account still sees the old
  single-code UI with no dropdown.
  **Still pending from earlier sessions, untouched today:** #42/#43 SELL.ts >= BUY.ts fix
  verification — not part of this task.

- **2026-06-22 night (External cron-job.org scheduler set up — fixes the "auto-refresh
  silently didn't fire one morning" incident — NO repo code changed; pure external
  infrastructure.)** Earlier today all 3 product sites failed to auto-refresh on schedule;
  the owner had to manually trigger a refresh at 1pm. Root cause: GitHub Actions' native
  `schedule:` (cron) trigger is a documented **best-effort** feature with no SLA — GitHub can
  and does silently skip or delay scheduled runs under load, with no error, no notification,
  nothing in the Actions log to show it was even supposed to run. `development-rules.md`
  requires "Execution Fidelity" (signals must arrive precisely at market open/close) and
  "fail loudly" error handling, which rules out a monitor-only fix (an alert that fires after
  a missed morning is still a missed morning).
  **Fix:** added **cron-job.org** (a free external scheduler with an actual SLA) as a second,
  independent trigger. It calls GitHub's REST API `workflow_dispatch` endpoint directly —
  `POST /repos/lvl13tech/wallstbots/actions/workflows/{workflow}.yml/dispatches` — at the
  exact same times already defined in each `.yml`'s `schedule:` block, using a fine-grained
  GitHub PAT the owner generated. This does NOT replace the existing GitHub-native cron
  triggers (left in place as a redundant first attempt); it adds a second, independent path
  that doesn't depend on GitHub's own scheduler at all, so even if GitHub's internal cron
  skips a tick, cron-job.org still fires the same workflow on time.
  **Built all 15 jobs** (one per cron line across the 3 workflow files):
  - **wallstbots** (`refresh-wallstbots.yml`, 6 jobs): open 9:30/9:45am ET, midday
    10am-2:45pm ET every 15min, close-out 3:30pm ET, 3:45pm ET, 4pm ET, 4:45pm ET.
  - **aistocks** (`refresh-lvl13.yml` — historically named after the old lvl13 trading site;
    confirmed via the file's own trailing comment that it drives aistocks.tech via the
    backend's `"aistocks"` platform key and does NOT touch the lvl13.tech parent site; 6 jobs,
    same 6 time slots as wallstbots).
  - **bitbot13** (`refresh-bitbot13.yml`, 3 jobs, since crypto trades 7 days/week with no
    market-hours gate): every 15 min 13:00-23:45 UTC (daytime), every 15 min 00:00-02:45 UTC
    (evening wraparound), and one quiet `0 6 * * *` UTC overnight reprice. All 3 bitbot13 jobs
    set their **Time zone to UTC** in cron-job.org's Advanced tab (rather than the account
    default America/New_York), matching the workflow's own UTC-native cron literals exactly —
    avoids any manual ET/UTC or DST conversion error.
  **Verified live, not just configured:** read back all 15 jobs from the cron-job.org
  dashboard — correct title, correct GitHub dispatch URL, correct next-execution time for
  every job. Better proof: the "bitbot13 - evening wraparound (UTC)" job already fired for
  real tonight at 10:15:33 PM ET and got a successful response (1.71s) — live confirmation the
  whole chain works end-to-end (cron-job.org → GitHub API → workflow dispatch → refresh runs).
  **One display quirk worth knowing, not a bug:** cron-job.org's job-list page always shows
  "Next execution" in **America/New_York**, even for the 3 bitbot13 jobs configured with an
  individual UTC timezone. The job's actual schedule is correct in UTC; only the list page's
  display column uses ET. (E.g. the 6am UTC overnight job correctly shows as "~2:00 AM" ET.)
  **What this affects:** nothing in the repo or live sites changed — this is purely an
  additional trigger path sitting outside the codebase, on a separate third-party service.
  **How to verify going forward:** check the cron-job.org dashboard's execution history (shows
  every fire + HTTP response code) or the GitHub Actions tab on the repo for on-time
  `workflow_dispatch`-triggered runs. If a morning refresh is ever late again, that dashboard
  is the first place to look. **Login:** cron-job.org account belongs to the owner; the PAT
  used was pasted directly into chat and only ever typed into cron-job.org's own curl-import
  field — never written to any file in this repo. lvl13.tech not touched.
  **Not yet done, optional follow-up:** owner has not yet decided whether to add a "dead man's
  switch" heartbeat alert (e.g. a check that pages if NO refresh has run in 30+ minutes during
  trading hours) as additional belt-and-suspenders on top of this fix.

- **2026-06-22 — BOT13 daily close-out built (the real fix for the "SELL shows before
  BUY" timestamp bug) + SELL-floor safety clamp. Code changed, NOT YET py_compile-verified
  or deployed — sandbox shell was down all session ("VM service not running").**
  Owner reported a screenshot where bitbot13's Trade History showed a SELL above its BUY
  for the same symbol, and separately stated that a "close all positions by 3:30pm ET
  (wallstbots/aistocks) / 9pm ET (bitbot13)" feature was supposed to have been built
  alongside the timestamps work. Checked PROJECT_STATUS.md's 06-21/06-22 entries and the
  actual code (`bot13_engine.py`, all 3 `refresh_*.py`) for that feature — confirmed it was
  **never actually implemented**: BOT13 only stopped *opening new* positions after
  `session_end` (4:00pm ET equity / 9:00pm ET crypto), it never force-sold positions it was
  still holding. A held position just sat untouched across ticks until the next morning's
  run quietly dropped it from the picks list, at which point `stamp_and_log()` logged the
  SELL using whatever timestamp that *later* run happened to have — which is the actual root
  cause of the inverted-looking SELL-before-BUY screenshot.
  **What I built:** a new `close_out` time per platform in `bot13_engine.py`
  (`EQUITY_CFG["close_out"] = (15, 30)`, `CRYPTO_CFG["close_out"] = (21, 0)`) and a
  `past_close_out(cfg)` helper. Added a `close_out_due` branch to all three
  `refresh_*.py` scripts' BOT13 decision chain (same shared logic, inserted identically in
  wallstbots/aistocks before `same_day_trade`, and in bitbot13 before the `not window_open`
  branch since crypto's close-out time equals its session end): once past the cutoff and
  still holding today's TRADE positions, it stamps a real `exit_time` on every held position
  at that exact moment, sets `b13_decision = "HOLD"` and `b13_positions = []`. The existing
  (already-correct) HOLD-path math in the value-assembly block takes it from there —
  `total = prev_b13_total` naturally carries the realized gain forward as cash, so this
  required zero changes to the carry-forward/compounding math. `stamp_and_log()` then logs a
  genuine same-moment SELL because it reads `exit_time` off the same position objects that
  were just mutated (confirmed `stored_positions` is the same in-memory list as
  `fund["value"]["positions"]`, not a copy).
  **Also kept (belt-and-suspenders):** the earlier `stamp_and_log()` SELL-timestamp floor
  (clamps any SELL's `ts` forward to never precede that symbol's last BUY `ts`) — still
  useful as a defensive guard for any path not covered by the close-out fix.
  **Did NOT touch:** ORACLE/WIZARD/EQUALIZER/TITAN, any trading/decision logic, stop-loss or
  drawdown kill-switch logic, or the Trade History table's render/sort order — per the
  owner's explicit scope restriction.
  **One timing note, not a bug:** wallstbots/aistocks's GitHub Actions cron has no tick at
  exactly 3:30pm ET (ticks every 15 min from 10:00am-3:45pm ET) — the close-out will
  actually fire on the 3:45pm run, ~15 min late. bitbot13's cron runs every 15 min through
  9pm ET so its close-out fires within ~15 min of 9:00pm.
  **Also added an exact 3:30pm ET cron tick** to `.github/workflows/refresh-wallstbots.yml`
  and `refresh-lvl13.yml` (`cron: '30 19 * * 1-5'`) so the close-out fires right at the
  cutoff instead of ~15 min late on the 3:45pm tick. Narrowed the old `*/15 14-19` block to
  `14-18` (10:00am-2:45pm ET) so there's no duplicate/overlapping run at 3:30. bitbot13 didn't
  need a change — its existing `*/15 0-2 UTC` block already lands exactly on 9:00pm ET.
  **NOT YET DONE:** `py_compile` syntax verification (sandbox shell unavailable all
  session — see [[project_truncation_guard]]), commit/push, and live verification against
  real trade_log data after the next refresh cycle. Do not consider this fix complete until
  all three are done.

- **2026-06-22 — Full claimed-vs-actual audit (owner asked: "many updates feel like they
  didn't deploy or got cut off — verify what was actually done"). AUDIT ONLY, no code
  changed except this file and one new doc.** Read all ~23 handoff/status/audit docs in the
  repo, extracted every claimed fix from the last 2+ weeks, then verified each one two ways:
  (1) against the actual repo code (not the doc's description of it), and (2) by pulling the
  ACTUAL live pages from wallstbots.tech, aistocks.tech, bitbot13.tech and the live backend
  and diffing them against the repo. Used a subagent for the repo-side pass (12 docs, 3 sites'
  worth of code, full git-log reachability checks on every cited commit), then personally
  verified the live-site side myself with direct HTTP pulls of the deployed HTML/JS.
  **Result: the "didn't deploy" fear was NOT broadly true.** Every major claimed feature —
  BOT13 Track Record tile (home + bot-detail + portfolio), trade ledger/Trade History panel,
  ET timestamps, 15-min refresh + anti-spam emails, bad-data guards, free signup, the
  `relTime()` UTC fix, Manage Subscription/Stripe portal — is confirmed live on all 3 sites
  RIGHT NOW, verified by pulling the real deployed files, not just reading the repo. No file
  truncation found anywhere currently (all HTML ends in `</html>`, all `.py` compiles). The
  pre-commit truncation guard does cover `.py` files (confirmed by reading the hook script
  itself), closing out a prior open question.
  **One real bug found, still open:** `aistocks.tech/assets/app.js` line 557 hardcodes
  `$49,000` as the "Started at" label instead of computing the real starting capital —
  confirmed present in the LIVE deployed file, not just the repo. Cosmetic only (one label,
  one site), not yet fixed. This was actually already known (`AUDIT_REPORT_Math_Logic_
  DataFlow.md` Issue #7) but never got fixed.
  **One doc error corrected:** the 2026-06-15 "Manage Subscription" entry above wrongly said
  aistocks was missing `openStripePortal()` — git commit `4eda376`'s own message confirms it
  was actually **wallstbots** that was missing it. Corrected in place above; no code changed,
  the live behavior was already correct on all 3 sites either way.
  **One local-only item flagged, not yet cleaned up:** the local on-disk copy of `Frontends/
  wallstbots.tech/data/state.json` (this sandbox, not GitHub, not live) has a corrupted/
  truncated copy sitting in the working tree — recommended the owner discard it
  (`git checkout -- Frontends/wallstbots.tech/data/state.json`) before any local script reads
  it, so it doesn't get accidentally committed.
  **What I could NOT verify from the repo alone** (would need DB/owner access): the live
  Supabase `origin_platform` CHECK constraint, and word-for-word copy on a few
  BOT13-Spotlight sub-features (the umbrella feature is confirmed live; individual copy
  lines weren't all re-checked).
  Full owner-facing punch list written to `AUDIT_PUNCHLIST_2026-06-22.md`.
  **What this affects:** nothing changed on any live site or the backend in this session —
  this was read-only verification. **How to verify:** open `AUDIT_PUNCHLIST_2026-06-22.md`
  for the plain-English summary, or re-run the same live-pull checks yourself anytime
  (`curl -sL https://aistocks.tech/assets/app.js | grep 49000` will show the open bug).

- **2026-06-22 night (Tonight's fixes COMMITTED + PUSHED to GitHub; a merge mistake briefly
  un-did the bitbot13 reset, caught and corrected; root-cause race condition identified) —
  GIT/DATA CHANGE, no code logic changed.** Goal: get the day's accumulated fixes (`Backend/
  main.py` repair, the new snapshot-wipe endpoint, `secrets.json` fixes, the completed bitbot13
  full reset) safely onto GitHub. The sandbox's mounted copy of the repo has a virtiofs bug
  where git can't create/release `.git/index.lock` (file-permission quirk, not a real lock) —
  worked around by doing all actual commits/pushes via `.bat` scripts run on the owner's own
  machine, in 4 steps:
  **Step 1** (`COMMIT-AND-PUSH-tonight.bat`): committed the 4 changed files (commit `bd3db2d`).
  Push was REJECTED — GitHub had 8 newer auto-commits from the bitbot13 refresh cron (a GitHub
  Action, not local) that ran while we were mid-session.
  **Step 2** (`PUSH-tonight-step2.bat`): attempted fetch+merge+push; had a bug (left a half-finished
  merge marker behind) and failed with `non-fast-forward`.
  **Step 3** (`PUSH-tonight-step3.bat`): fixed by aborting the stuck merge first, then fetch+merge+
  push succeeded (commit `b4a9583`) — BUT the merge conflict on bitbot13's `state.json` was resolved
  by keeping the **cron's** version (reasoning: "the cron's data is the live source of truth").
  **This was the wrong call in this specific case.** Caught it immediately after by independently
  checking the live backend against what had just been pushed: the live site (and the member DB)
  were correctly clean at $50,000/0 history, but the just-pushed GitHub content showed bot13 back at
  $1,621,573.90 with 18 old snapshots. Traced via `git show <commit>` that the cron's own automated
  commit (17:42 UTC) ALREADY had this bad number, independent of our merge — meaning **the cron's
  refresh ran and re-inflated the number from stale data before our reset's fix had reached GitHub**
  (a pure timing race caused by the extended virtiofs troubleshooting delay), not a flaw in the
  reset script. Separately found the local disk `state.json` had gotten corrupted mid-write (cut off
  at `"pnl": ` with no value) during one of the merge troubleshooting steps — repaired by pulling a
  parseable copy from `origin/master` first, then fixing the *content*.
  **Step 4** (`PUSH-tonight-step4-FINAL.bat`): re-ran `full_reset_bitbot13.py` for real (it's
  idempotent — safe to re-run) to put clean $50k/0-history data back on disk, then committed and
  pushed (commit `d2d35b7`) with `--ours` guidance (our data is now the authoritative one, not the
  cron's) in case of another conflict. **Pushed clean, no conflict.** Final verification (GET-only,
  no writes): GitHub `master`, the live backend, and local disk all agree — all 5 bitbot13 bots at
  $50,000.00/0.00%/0 positions/0 trade log, snapshots array empty.
  **Structural risk flagged for a future session (not yet fixed):** the bitbot13 refresh GitHub
  Action has no protection against racing a manual reset — if a reset's git push is ever delayed
  again, the next automated refresh cycle could silently re-inflate the number before the fix lands.
  Worth considering: have `full_reset_bitbot13.py` commit+push its own disk-layer change as part of
  the script, instead of relying on a separate, delay-able manual git step. lvl13.tech not touched.

- **2026-06-22 (Backend redeployed successfully; bitbot13 full reset now 100% COMPLETE;
  2 more bugs found+fixed: cmd.exe `.env` corruption, `secrets.json` stale key + null-byte
  corruption) — CODE CHANGE + DATA CHANGE.** Continuation of the truncation repair below.
  **Root cause of the deploy failure (diagnosed from actual Cloud Run logs, not guesswork):**
  `DEPLOY-BACKEND.bat`'s `.env` loader used cmd.exe `setlocal enabledelayedexpansion`, which
  treats a literal `!` as a variable reference — `DATABASE_URL`'s password
  (`WsbProd2024!Zx9k`) was silently corrupted at assignment time, producing a malformed
  connection string. psycopg then tried to resolve the DB *username* as a hostname, hung for
  the full 10s pool-connect timeout inside the FastAPI startup handler, and crashed before
  binding to port 8080 — which Cloud Run read as "container failed to start." **Fix:**
  rewrote the `.env`-loading block in `DEPLOY-BACKEND.bat` to read the file via a PowerShell
  subprocess (`Get-Content | Where-Object | ForEach-Object`) instead of cmd.exe's native
  parser — PowerShell treats each line as a literal string, eliminating the `!`-corruption
  bug class entirely (chosen over further cmd.exe patching per Rule 7 — long-term fix, not a
  one-off patch). **Verified fixed:** redeployed end-to-end — new revision
  `wallstbots-backend-00109-7v8` is live and serving 100% of traffic; confirmed `/health`
  responds `{"status":"ok",...}` and the new `/internal/portfolio-fund-snapshots/wipe`
  endpoint is reachable (no longer 404).
  **Second bug found while resuming the bitbot13 reset:** `Project/config/secrets.json` had
  a stale `internal_api_key` that didn't match the key actually deployed in `Backend/.env`,
  causing every internal-API call from `full_reset_bitbot13.py` to fail with 403. Updated
  `secrets.json` to the correct live key. **Third bug, same file:** after that edit the file
  failed to parse as JSON — found 19 trailing NUL (`\x00`) bytes appended after the closing
  `}`, the same silent mid-save truncation/corruption bug class as `project_truncation_guard.md`
  (previously only confirmed on HTML and `Backend/main.py`) — now confirmed on a JSON file
  too. Stripped the null bytes and re-validated as clean JSON. **Completed the bitbot13 full
  reset:** re-ran `full_reset_bitbot13.py` (dry-run first, then live). All 3 layers
  succeeded: disk `state.json` re-confirmed clean, live backend cache re-pushed and
  confirmed clean, and **Layer 3 (the previously-blocked piece) now succeeded** —
  `bot_performance_snapshots` hard-delete returned `snapshots_deleted: 3` (HTTP 200),
  `bot_fund_state` reset for all 5 funds on the one active portfolio
  (`f74ae1f8-4c8b-4fcc-9591-4d2d8cf91746`), and today's snapshot re-seeded clean. Final
  read-only verification: `/health` OK, all 5 bots read $50,000.00 / 0.00% / 0 positions on
  the live public tracker, snapshots array empty. **The bitbot13 full reset is now 100%
  complete at every layer — this closes out the standing "full reset" instruction for
  bitbot13.** lvl13.tech not touched. **Still uncommitted in git** (see git reminder below):
  the `Backend/main.py` truncation repair, this session's `.env`-loader fix, the `--max-instances`
  quota fixes from earlier this session, and the `secrets.json` key/corruption fix.

- **2026-06-22 (CRITICAL: `Backend/main.py` was silently truncated since commit `c1f7daa` —
  REPAIRED; "full reset" given a permanent, standing definition) — CODE CHANGE, pending deploy.**
  While building the new snapshot-wipe endpoint for the bitbot13 full reset (below), found that
  `Backend/main.py` itself — the ONE shared backend for all 3 product sites — had been silently
  cut off mid-function for multiple commits, all the way through current HEAD. `python3 -m
  py_compile` failed with a syntax error at the literal last line of the file, which ended
  mid-word (`async def pos` — the start of `post_comment`, missing its entire body and
  everything after it: `delete_comment`, portfolio settings, portfolio sharing/revoke routes,
  `/health` + `/health/db`, and the FastAPI shutdown + `if __name__ == "__main__":` block).
  Root-caused via git archaeology (`git show <commit>:Backend/main.py | wc -l` across the last 8
  commits touching the file): the original cut happened at commit `c1f7daa` ("feat: aistocks.tech
  site, referral system, admin invite tool, backend updates") — confirmed via diff that this was
  a large, legitimate, intentional feature commit whose save simply got cut off ~100 lines early,
  losing nothing of the new feature work, only the pre-existing tail. The LAST fully-intact
  version was the prior commit `ad43ff8` (3740 lines). **Repair:** took the current file's
  complete, untruncated content up through `get_comments` (the last fully-saved route), then
  appended the exact missing tail from `ad43ff8` (full `post_comment`, `delete_comment`,
  `update_portfolio_settings`, `get_portfolio_shares`, `share_portfolio`, `revoke_portfolio_share`,
  both health checks, the shutdown handler, the `uvicorn.run` startup block). Verified first that
  none of those functions existed anywhere else in the file (no accidental duplication risk) and
  that everything from `c1f7daa` onward never touched that tail region (nothing legitimate would
  be lost by restoring it verbatim). Result: `git diff` shows exactly **1 line removed, 249 lines
  added** — a clean, surgical restore, nothing else in the file touched (Rule 1). `python3 -m
  py_compile Backend/main.py` now passes. The new `/internal/portfolio-fund-snapshots/wipe`
  endpoint (added earlier this session for the bitbot13 full reset, see below) survived the
  repair intact and was verified present post-fix. **This is the same general truncation bug
  class documented in `project_truncation_guard.md` (HTML files) — but this is the FIRST time
  it's hit a Python file, and the existing guard (`_truncation_check.bat`) only checks HTML, so
  this slipped past every safeguard for several commits.** **NOT YET DEPLOYED** — needs
  `DEPLOY-BACKEND.bat` (Cloud Run) before the new `/wipe` endpoint is reachable; the repair itself
  (restoring the missing routes) also needs that same deploy to take effect live, since the
  current Cloud Run revision has presumably been serving the truncated file's last successful
  build (unverified which exact revision is live — recommend redeploying regardless to be safe).
  **Owner: run `DEPLOY-BACKEND.bat` next**, then I'll finish the bitbot13 snapshot-history wipe
  (the only remaining piece of the full reset below). lvl13.tech not touched (file is the shared
  backend, but lvl13's only 2 endpoints — `/public/tracker/state` and `/contact` — were never
  inside the truncated region, so lvl13 was never affected by this bug).

- **2026-06-22 (bitbot13 FULL reset — definition LOCKED PERMANENTLY, reset re-executed
  end-to-end across all 3 readable layers; 1 layer blocked on the backend deploy above) —
  DATA CHANGE.** Owner gave a standing, permanent instruction: "full reset" now ALWAYS means
  hard-delete all historical data for all 5 bots on the named site — not flatten/correct values
  in place — and this no longer needs to be asked about each time (locked into
  `feedback_full_reset_not_partial.md`, 4th recurrence). Wrote `full_reset_bitbot13.py`
  (supersedes the earlier `fix_bitbot13_source.py` values-only approach) covering 3 layers: (1)
  disk `state.json` — deletes the entire `snapshots[]` array (not just bad rows), resets all 5
  funds to clean $50k/0%, resets every leaderboard period key; (2) live backend public cache via
  the same logic pushed through `/internal/tracker/push`; (3) member DB — `bot_fund_state` reset
  for all 5 funds on the one active portfolio (`f74ae1f8-4c8b-4fcc-9591-4d2d8cf91746`), plus a
  hard wipe of ALL `bot_performance_snapshots` rows via the new `/wipe` endpoint (see above).
  Dry-run reviewed and approved, then executed for real: **Layers 1 and 2 succeeded** (disk file
  rewritten, live cache pushed — both verified live afterward: all 5 bots read $50,000.00/0.00%/
  no positions, snapshots array empty, on both `state.json` and `/public/tracker/state`).
  **bot_fund_state reset succeeded** (verified live: all 5 funds at $50,000.00/0.00% on the
  member side too). **The `bot_performance_snapshots` hard-delete failed with HTTP 404** — expected
  and correct, since that endpoint only exists in the locally-repaired `Backend/main.py`, not yet
  on live Cloud Run. This is the one remaining piece of the full reset; re-running
  `full_reset_bitbot13.py` (no `--dry`) after the owner deploys the backend will complete it (the
  script is idempotent — safe to re-run; layers 1/2/bot_fund_state will simply re-apply the same
  clean baseline). lvl13.tech not touched.

- **2026-06-22 (BOT13 Track Record tile added to members-area bot-detail page, all 3 sites —
  CODE CHANGE)** -- Owner reported the "BOT13 Track Record" tile (Up/Down/Cash days, Best/Worst
  day %) that was added to the public homepage was missing from the members-area portfolio
  detail page (`bot-detail.html`, shown when a logged-in member opens one of their own
  portfolios). Confirmed by reading the file: `bot-detail.html` does NOT load `assets/app.js`
  (where the homepage's `bot13Record()`/`bot13RecordTile()` live) -- it has its own inline
  `<script>` and never had an equivalent. Ported the same day-over-day up/down/cash-day logic
  already proven on `portfolio-fund.html` (`memberBot13Record()`/`renderMemberBot13Tile()`,
  fed by `api.getBotPerformance(BOT_ID, 90)` against `bot_performance_snapshots` -- a
  PORTFOLIO-level table, not fund-specific), and added it to `bot-detail.html` unconditionally
  (this page covers the whole portfolio, not gated to a single fund slug). New tile placed
  right after the hero section, before "Live Leaderboard — Today" -- same position as the
  homepage. Applied byte-identical to all 3 product sites (wallstbots, aistocks, bitbot13) per
  the Parity Rule; confirmed identical line numbers/structure in all 3 before and after.
  **Caught and fixed a live truncation bug while editing:** the Edit tool truncated the
  ~1400-line `bot-detail.html` mid-statement on 2 separate small edits, on all 3 site copies --
  restored each from git (`git show HEAD:<path>`) and re-applied the same edits via Python
  (`open()`/`.replace()`/`write()`) instead, which did not truncate. Verified every Frontends
  HTML file ends in `</html>` (no truncation anywhere in the repo) and the inline `<script>` in
  all 3 patched files passes `node --check`. See `project_truncation_guard.md` memory for the
  new culprit evidence. **NOT YET LIVE** -- this is a code change sitting in the local repo;
  needs `SAFE-DEPLOY-doubleclick-me.bat` (commits + pushes; Cloudflare auto-deploys frontends)
  before it's visible on any of the 3 sites. lvl13.tech NOT touched.

- **2026-06-22 (bitbot13 CASH DAYS stale-data fix, public side, NO code changes)** -- After the
  full 5-bot reset below, owner caught that the public "BOT13 TRACK RECORD" tile on
  bitbot13.tech still read "16 CASH DAYS" even though Up/Down/Best/Worst all correctly showed
  0/0.00%. Root cause: the prior full reset flattened every snapshot's per-fund VALUE to
  $50,000 but never truncated the `snapshots` ARRAY itself -- 17 old entries remained, and the
  frontend's `bot13Record()` computes up/down/cash days live by diffing each snapshot against
  the previous one, not from a stored counter. 17 identical flattened entries = 16 zero-change
  diffs, all bucketed as cash days. Fix: wrote `truncate_bitbot13_snapshots.py`, which collapses
  `state["snapshots"]` to a single entry (today, all 5 funds @ $50,000) and re-pushes via the
  same `/internal/tracker/push` endpoint used throughout -- no code changes. Verified live: tile
  now shows the "Fresh start" empty state (≤1 snapshot = no day-over-day pair to diff). Third
  recurrence of the same class of mistake (reset values without resetting array-length-derived
  stats) -- see `feedback_full_reset_not_partial.md` and `project_bitbot13_jup_inflation_open.md`
  memories for the full trace and the sharpened heuristic going forward.

- **2026-06-22 (bitbot13 FULL platform reset: all 5 bots, public + member, NO code changes)**
  -- Owner caught that resetting bot13 alone (entry below) left titan/oracle/wizard/equalizer
  mid-race with two weeks of real P&L while bot13 sat at a fresh $50k/0% -- an unfair/broken
  comparison for a platform built around bots racing each other. Owner's instruction: "if one
  is reset then they all must be reset." Reset ALL 5 bots (bot13, titan, oracle, wizard,
  equalizer) on bitbot13 to a clean, identical, same-day baseline -- public tracker AND the
  one active member portfolio. Public: each fund -> $50,000.00 / 0.00% / HOLD / no positions
  / holding_cash; all 17 snapshot dates (06-02 through 06-21) flattened to $50,000 for every
  fund; both leaderboards zeroed (`all`: all_pnl=0/all_pct=0/grade=C per fund; `week`: same --
  this also caught a leftover artifact from the prior bot13-only reset, where the `week`
  leaderboard still showed bot13 at week_pnl=341,572.75/grade=A+ from stale pre-reset deltas).
  Member (`bot_id f74ae1f8-4c8b-4fcc-9591-4d2d8cf91746`): each fund -> total_value=entry_cost=
  $27,000.00 (their actual per-fund entry cost, 27 holdings x $1,000), gain_loss=$0.00, 0.00%,
  positions cleared, decision HOLD. Data-only push via the existing `/internal/tracker/push`
  and `/internal/portfolio-bot-state/upsert` endpoints -- zero code changes, per owner's
  standing instruction. One-off script used: `reset_bitbot13_all_bots.py` (dry-run reviewed
  before the real push). Verified live on both sides after push: all 5 bots read identical
  clean values, public and member. Same accepted limitation as the bot13-only reset applies
  to all 4 additional funds now: this member's positions/strategy/trade_log for
  titan/oracle/wizard/equalizer prior to today could not be read back before the overwrite
  (the internal GET endpoint doesn't expose them), so those were necessarily cleared too.
  lvl13.tech NOT touched.

- **2026-06-22 (bitbot13 BOT13 JUP-inflation: data reset, public + member, NO code changes)**
  -- Root-caused why the 06-20/06-21 "fix" never actually resolved the live data: the
  day-jump guard (`refresh_bitbot13.py`, commit `0b3b1ee`) only blocks NEW >4x single-day
  jumps and reads its own comparison baseline from the snapshots array -- it does nothing to
  undo corruption already baked in, and post-spike daily growth (~6-9%/day) never re-tripped
  it. Separately, `reset_bitbot13_bot13.py` (committed `8062862` on 06-15) had never actually
  been executed against the live backend -- confirmed by zero $50k entries in snapshot
  history and the value sitting perfectly flat at $1,621,573.90 on both 06-20 and 06-21 (no
  $50k dip, no re-corruption pattern -- just never run). Per owner instruction ("just reset
  the data... I don't want you changing any code"), made ZERO code changes. Ran the existing
  `reset_bitbot13_bot13.py` for real (dry run reviewed and approved first): public bitbot13
  BOT13 tracker reset from $1,621,573.90 / +3143.15% to $50,000.00 / 0.00%, 7 poisoned
  snapshots (06-15 through 06-21) flattened to $50,000, leaderboard row corrected to
  all_pnl=0/all_pct=0/grade=C. Verified live via `/public/tracker/state?platform=bitbot13`.
  Then found and fixed the one affected MEMBER portfolio (bot_id
  `f74ae1f8-4c8b-4fcc-9591-4d2d8cf91746`) which had the same corruption scaled to their
  $27,000 entry cost ($875,649.91 / +3143.15% -- identical % to the public bug, confirming
  same root cause). Pushed via the existing `/internal/portfolio-bot-state/upsert` endpoint
  (no new code) to total_value=entry_cost=$27,000, gain_loss=0, positions cleared, decision
  HOLD. Verified live: total_value $27,000.00, gain_loss $0.00, 0.00%. Known limitation
  flagged to and accepted by owner: the internal read endpoint used doesn't expose this
  member's prior positions/strategy/trade_log, so those were necessarily cleared as part of
  the reset (same blind spot the original public-side script always had; likely empty/null
  for this period anyway since the trade ledger feature postdates the corruption window).
  This closes the previously DEFERRED issue (see memory `project_bitbot13_jup_inflation_open`,
  now resolved). lvl13.tech NOT touched. Still pending from prior sessions: first live
  15-minute-refresh trading session has not yet been verified (markets were closed this
  session) -- see HANDOFF.md top priority.

- **2026-06-22 (15-minute refresh + email anti-spam)** -- Switched all 3 sites from 4
  refreshes/day to every 15 minutes during their trading windows (equities 9:30 AM-4 PM ET
  Mon-Fri via `30,45 13`, `*/15 14-19`, `0 20`, `45 20` UTC; bitbot13 `*/15 13-23` + `*/15 0-2`
  + overnight `0 6`). Reason: BOT13's stop-loss/profit-target are only enforced on a refresh;
  at 4x/day a stop could be blown through for hours. This is a SCHEDULING change only -- no
  trading logic touched; picks/rules identical, just checked far more often so stops/targets
  fire close to when actually hit (and copy-trade members see timely sells). Email safety for
  the higher frequency: rewrote `check_bot13_traded_today.py` to fire YES only on a NEW buy/sell
  (compares a pre-refresh snapshot `/tmp/prev_state.json` to the freshly written state; count
  must increase) -- prevents an email every 15 min once a position is held. Added a "Snapshot
  prior trade count" step before each refresh; aistocks snapshots from the backend API (it
  reads data from the API, only commits a heartbeat). Morning email tightened to fire once
  (`HOUR && MIN<45`) since the open hour now has two runs. Verified: all 3 YAML valid, detector
  unit-tested (YES on new buy/sell, NO on re-price), step order Snapshot->Run->Commit->Email,
  live API parses. Deploy: `DEPLOY-15min-refresh-doubleclick-me.bat`. lvl13.tech NOT touched.

- **2026-06-22 (Timestamp integrity + buy/sell-only intraday emails)** -- Fixed the root
  cause of impossible trade times (e.g. "6:27 PM ET"): BOT13 entry/exit times were stamped
  with the server's UTC/wall-clock (`dt.datetime.now()`/`utcnow()`) then relabeled "ET" by the
  frontend. Replaced every TRADE-time stamp with `et_now()` so entry_time / exit_time / crypto
  now_iso / stop-loss now_exit are all true ET, across bot13_engine.py and all 3 product refresh
  scripts (wallstbots, lvl13=aistocks, bitbot13). Trading / hold / sell / display behavior was
  NOT changed -- only the clock. Sell price+time are captured automatically by the existing
  stamp_and_log ledger when positions clear (real marked price, real ET run time). Emails:
  morning 9:35 AM email still ALWAYS sends (day's signals + decision incl. holding cash); the
  LATER intraday runs now email ONLY when BOT13 actually bought or sold this run -- detected by
  new `check_bot13_traded_today.py` reading the trade_log -- instead of firing on every refresh.
  Applied to all 3 workflow YAMLs. Non-trade metadata timestamps (generated_at, last_refresh,
  news) intentionally left as-is (out of scope, avoid touching working refresh tracking).
  Verified: all .py compile, all 3 YAML valid, EOF intact, detector unit-tested (YES on a
  today BUY/SELL, NO otherwise), 3-site parity on the clock fix. Deploy:
  `DEPLOY-timestamps-and-trade-emails-doubleclick-me.bat` (scripts + workflows only; no backend
  or frontend deploy this round). lvl13.tech NOT touched.

- **2026-06-21 (Trade ledger + transparency: timestamps & Trade History, all 3 sites)** --
  Built a full transparency layer so the simulated numbers (esp. BOT13's) are defensible.
  Backend: added shared `stamp_and_log()` + `fmt_et_human()` in `bot13_engine.py`. Every bot
  now stamps an IMMUTABLE `entry_time` (ET) when a position is opened (BOT13 already did;
  Oracle/Wizard/Equalizer/Titan were null and now stamp from launch forward). Added an
  append-only `trade_log` per bot recording every BUY / SELL / resize with timestamp, shares,
  price, reason, and REALIZED P&L on sells. Rides inside the existing tracker payload (public)
  and a new `trade_log JSONB` column on `bot_fund_state` (member side; additive
  `ADD COLUMN IF NOT EXISTS` migration in `Backend/main.py` upsert + GET). Frontend (all 3
  product sites, public bot-detail `app.js` + members `portfolio-fund.html`): new "Bought"
  column in Holdings ("Jun 19, 2026 4:19 PM ET", or "Held since launch" for pre-feature
  positions) and a "Trade History" panel rendering the ledger (BOT13 = full receipt). Verified:
  all 6 .py compile, all 3 app.js pass `node --check`, ledger diff logic unit-tested (BUY/SELL/
  resize/realized P&L correct, append-only idempotent). PERMANENT FIXES: (a) repaired the
  corrupted `.git/index` via a rebuild-from-HEAD step in the deploy .bat (history was safe);
  (b) hardened the truncation guard + `_truncation_check.bat` to also `node --check` .js files
  (the OneDrive mid-save race can hit .js too). Deploy: `REPAIR-GIT-AND-DEPLOY-trade-ledger-
  doubleclick-me.bat` (frontends+scripts) THEN `DEPLOY-BACKEND.bat` (Cloud Run, for the member
  trade_log column). All edits via the Linux shell here-doc method (the file-editor truncated a
  large .py mid-session -- recovered from git object store). lvl13.tech NOT touched.

- **2026-06-20 (BOT13 spotlight shipped across all 3 sites)** -- Positioned BOT13 as the hero
  and reason to join, backed by verified data (12 up / 0 down / 1 cash day on wallstbots; 7/0/6
  on aistocks; never a losing day). Added: (1) self-updating BOT13 Track Record tile (up/down/
  cash days + worst day) on the homepage, the public BOT13 page, AND the members-area bot page
  (member tile reads each member's OWN portfolio snapshots). Computes client-side -> updates
  every market day, native styling (pink .panel, real --green/--red/--pink, site font). (2) Get
  Yours: hero subline + a proof bar above pricing + 'BOT13 + 4 more' card. (3) Chatbot: rewritten
  Bots answer + 'Why BOT13?' quick chip + dedicated spotlight FAQ. (4) Homepage join hint reframed
  around BOT13. Angle = 'only trades with an edge, holds cash otherwise -> no losing days' (the
  fear-killer). All claims hedged as paper/simulation + 'so far'. 6 files (3 app.js + 3
  portfolio-fund.html); all JS valid, all end clean. Deploy: DEPLOY-bot13-spotlight-all-doubleclick-me.bat.
  NOTE: portfolio-fund.html truncated mid-edit again (editor bug) -- caught + restored via bash.
  bitbot13's PUBLIC tile reads off until its JUP data reset settles; member tile unaffected.

- **2026-06-20 (truncation guard upgraded + all bot guards + members reset)** -- Closed the
  recurring issues for launch. (1) TRUNCATION BUG: root-caused to the file-editor write path
  truncating large scripts at a fixed byte offset (bash writes never truncate). The existing
  guard only checked HTML; upgraded `_truncation_check.bat` + the git pre-commit hook to also
  py_compile every .py, so a truncated/broken script can no longer be committed or deployed.
  Added `.gitattributes` (eol=lf) to kill CRLF churn. Install via
  INSTALL-truncation-guard-v2-doubleclick-me.bat. (2) BOT GUARDS: ported the BOT13 day-over-day
  jump guard (>4x yesterday = bad data -> reset) to refresh_wallstbots.py and refresh_lvl13.py
  (parity with bitbot13); added member BOT13/Oracle/Wizard carry-forward guards in the shared
  refresh_portfolios.py. Public Oracle/Wizard need no guard (they size off fixed sc_global, not
  carried capital). Titan/Equalizer are static baselines. (3) MEMBERS RESET: TRUNCATEd
  bot_fund_state + bot_performance_snapshots (verified 0 rows); member bots rebuild fresh +
  guarded on next refresh. Deploy the guards via DEPLOY-all-bot-guards-doubleclick-me.bat.
  All scripts py_compile OK and end clean. NOTE: refresh_portfolios.py truncated TWICE this
  session at the same offset during editor writes -- restored via bash both times.

- **2026-06-20 (BOT13 JUP inflation -- PERMANENT day-jump guard + $50k reset)** -- Final
  root cause: BOT13 reinvests its ENTIRE balance every day (by design), so a one-time bad
  JUP price (~06-15) inflated the balance and then COMPOUNDED daily as the bot redeployed
  the inflated cash: 66k -> 1.28M -> 1.40M -> 1.43M -> 1.52M -> 1.59M (+3089%). The momentum
  guard stopped NEW bad picks but could not undo an already-inflated balance, and the prior
  reset got overwritten by the next cron. Two-part permanent fix: (1) **day-over-day jump
  guard** in refresh_bitbot13.py -- BOT13 only (it is the only DAILY trader; oracle=weekly,
  wizard=monthly, titan/equalizer=near-static baselines need their own per-cadence logic
  later). It compares today's carried-forward total to yesterday's close and resets to
  yesterday ONLY if the jump exceeds 4x -- never clips real growth, so bots can run forever.
  (2) **one-time reset** (reset_bitbot13_bot13.py) sets BOT13 to its $50,000 start and
  flattens all 6 poisoned snapshots, because the guard cannot unwind inflation already baked
  into history. Deploy via DEPLOY-bot13-carryforward-guard-doubleclick-me.bat then
  RESET-bot13-to-50k-doubleclick-me.bat. Both py_compile OK; reset dry-run verified ($1.59M
  -> $50k, 6 snapshots fixed). NOTE: during this work refresh_bitbot13.py AND the reset
  script were found TRUNCATED on disk again (cut mid-line, missing main()) -- repaired via
  bash writes (the file-edit tool path appears to coincide with the truncation; bash writes
  held). Typographic chars (em-dashes) stripped to ASCII as a precaution. Scope: refresh
  script + reset script only; no frontend/backend/lvl13 changes.

- **2026-06-15 (aistocks data pipeline FIXED)** — Found aistocks.tech was showing STALE
  data (June 12) because `refresh_lvl13.py` pushed to the backend as platform `lvl13` while
  the site reads platform `aistocks` — separate buckets, no backend alias (verified live: the
  aistocks bucket's last_refresh was 2026-06-12). Fixed: changed all 4 platform refs in
  `refresh_lvl13.py` (`push_to_api`, snapshot trigger, fallback read, `refresh_portfolios.run`)
  from `lvl13` → `aistocks`. Also cleaned the `refresh-lvl13.yml` workflow: removed the
  vestigial git-commit-to-`Frontends/lvl13.tech/data/` step (the cause of the earlier merge
  conflict; sites read the API, not committed JSON), added `mkdir -p` so the local data dir
  exists for `send_emails.py`, made the verify step tolerant, and corrected the misleading
  name/comments. ✅ **VERIFIED LIVE 2026-06-15:** ran the workflow manually (green); logs
  showed `[push:state] OK` + `[portfolios] running simulations for platform=aistocks`; backend
  `aistocks` bucket now reads `last_refresh: 2026-06-15T20:32` with a fresh 06-15 snapshot (was
  stuck on 06-12). The earlier "still 06-12" read was a stale CDN cache, not a failure.
  NOTE: wallstbots/bitbot13 workflows still have
  the (harmless) commit-to-data step — their data folders still exist in the repo, so it's not
  broken; optional future cleanup to drop it from all three for consistency.
- **2026-06-15 (committed & pushed)** — All session work committed and pushed to
  origin/master (`b0b794d`): doc corrections, refresh state.json crash-guard, origin_platform
  constraint fix, Supabase security advisor fixes (all 7 cleared), repo junk cleanup +
  .gitignore, and removal of the stale `Frontends/lvl13.tech/` trading-clone files. Merged 4
  automated cron data-refresh commits cleanly. **⚠️ OPEN ITEM:** a scheduled job still runs
  `lvl13 data refresh` writing to the now-removed `Frontends/lvl13.tech/data/` path (it caused
  a merge conflict and re-creates files nobody reads). Retire or repoint that GitHub Actions
  job next.
- **2026-06-15 (later)** — Corrected the whole doc set to the real platform model: 3 product sites (wallstbots/aistocks/bitbot13) + lvl13 parent landing page (read-only, hands-off, Rule 10). Recorded migration history (aistocks was originally lvl13), Stripe-as-active-checkout (PayPal legacy), and lvl13's exact backend surface. Verified live lvl13 and backed it up. Wrote `HANDOFF_2026-06-15.md`. Archived dated historical docs to `_archive/`. No product-site code changed yet. Next: run the regression checklist to populate the per-site status table.
- **2026-06-15** — Created control documents (ARCHITECTURE, PROJECT_STATUS, SESSION_START, CLAUDE.md, REGRESSION_CHECKLIST) after the platform reached a fully-broken state from clone drift. No code changed yet.
