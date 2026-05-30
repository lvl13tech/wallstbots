# Handoff — Bot13 "Projected Return" fix (lvl13.tech)

**Date:** 2026-05-29
**Owner:** M13 (lvl13cs@gmail.com)
**Scope:** lvl13.tech Bot13 page not showing the Projected Return box; data integrity of the lvl13 tracker.

---

## TL;DR / current status

- **Root cause is fully diagnosed** (below). The frontend code was never the problem.
- **Two fixes are complete and durable** (legacy pusher disabled in code; problem understood).
- **One action is IN A BROKEN INTERMEDIATE STATE and needs finishing:** an `INTERNAL_API_KEY`
  rotation left the **GitHub Actions secret and the Cloud Run env var not matching**, so the
  lvl13 refresh pipeline is currently returning HTTP 403 on every push. As a result the live
  lvl13 bot13 data is **frozen** (last good write `2026-05-29T13:30:02`, old schema, no box).
- **The site is up for visitors** (the public read endpoint needs no key); only the behind-the-scenes
  refresh is failing. Fixing the key match (or applying the recommended backend guard) restores it.

---

## The original problem

On `lvl13.tech` the Bot13 page (`/#/fund/bot13`) did not show the **Projected Return** box, and
historical data looked suspect. `wallstbots.tech` showed it fine. The two sites are supposed to be
identical except for the assets they trade.

## Root cause (confirmed)

1. **Frontend is identical and correct** across all three sites. The box renders only when the
   bot13 strategy object contains a `projected_return` field:
   `app.js → renderStrategyPanel()` → `projHtml = (projRet != null) ? <box> : ''`.

2. **The live data comes from a shared backend**, not static files:
   `https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker/state?platform=lvl13`
   (Cloud Run service `wallstbots-backend`, project `lvl13-tracker-496402`, region `us-east1`).
   It serves whatever was last pushed into the Postgres table `tracker_live_data (data_type, platform)`.

3. **Two different pipelines were writing the `platform=lvl13` row:**
   - **Correct pipeline:** GitHub Action **"Refresh lvl13.tech"** → `Project/scripts/refresh_lvl13.py`
     → `bot13_engine.py`. This emits the modern schema **with `projected_return`**.
   - **Legacy "zombie" pipeline:** `Project/scripts/refresh_data.py` (the original AIQC Tracker /
     HostGator-era script). It pushed the **old schema** (keys `scored_universe`, `skipped`, **no
     `projected_return`**) to `platform=lvl13` using the shared `INTERNAL_API_KEY`.

4. The legacy pipeline kept overwriting the good data (observed reverts at ~12:10 and ~13:30 ET),
   which is why edits "never showed up live." The legacy `scored_universe`/`skipped` schema exists in
   **no current script** in the repo — it comes from an older deployed copy, almost certainly a
   **leftover HostGator cron** (there is **no** Windows Scheduled Task on the PC — verified by scanning
   all 294 tasks; and the AIQC desktop app `RUN_FUND_TRACKER.py` does **not** push to the backend).

## What was completed

- **Confirmed frontend parity** lvl13 vs wallstbots (byte-identical render logic).
- **Disabled the legacy backend push** in both copies of `refresh_data.py` so they can never clobber
  live data again (early-return guard added to `push_to_api`):
  - `C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\Project\scripts\refresh_data.py`
    (committed locally as `32e2b2d`; push to GitHub still pending — see "loose ends").
  - `C:\Users\temps\OneDrive\Desktop\Claude\Websites\1. lvl13.tech\Project\scripts\refresh_data.py`
    (plain folder, not git — edit is permanently durable there).
- **Verified the GitHub Action pipeline works** (it pushed correct new-schema data with
  `projected_return` earlier — the box appeared at `projected_return: 16.64`), proving the only
  remaining issue is the legacy writer + the key rotation we were attempting as the lockout.
- **Backend confirmed to enforce the key:** `Backend/main.py → verify_internal_key()` returns 403 on
  mismatch (500 if the server key is empty). The push endpoint is `/internal/tracker/push`.

## The unfinished / broken bit — INTERNAL_API_KEY rotation

The plan was to rotate `INTERNAL_API_KEY` so the legacy script's old key is rejected (403) while the
GitHub Action uses the new key. Execution went wrong because the value had to be entered in two places
(GitHub repo secret **and** Cloud Run env var) and they ended up **not matching**. Evidence: the
"Refresh lvl13.tech" run log shows:

```
[push:state]   HTTP 403: {"detail":"Invalid internal key"}
[push:signals] HTTP 403: {"detail":"Invalid internal key"}
```

Because of this mismatch, **no writer can currently update the lvl13 row**, so the live page is frozen
on the last legacy write (`13:30:02`, no Projected Return box).

Important suspicion to check first: in the Cloud Run "Edit & deploy new revision → Variables & Secrets"
tab, the `INTERNAL_API_KEY` **value field displayed blank** every time (while other vars like
`POLYGON_API_KEY` showed their values). That strongly suggests **`INTERNAL_API_KEY` is wired to Google
Secret Manager (a secret reference), not an inline env value** — meaning edits to that inline field did
nothing, and the real value lives in Secret Manager. This would explain why every rotation attempt
failed to take.

### Two candidate key values in play
- The **original** key (worked this morning on both sides).
- A **new** key generated during the session (64-hex). Both values were shared in the chat; they are
  intentionally **not written into this file** for security.

---

## How to finish (pick ONE)

### Option A — Make the two keys identical (quickest restore)
1. Determine the **actual** value the backend is using:
   - Check whether `INTERNAL_API_KEY` is a **Secret Manager reference**: Cloud Run service →
     **YAML** tab → look under `spec.template.spec.containers[].env` for `INTERNAL_API_KEY`. If it shows
     `valueFrom: secretKeyRef:` it's a Secret Manager secret — edit the secret's value in
     **Security → Secret Manager**, not the inline field. If it shows `value: <key>`, that's the literal
     backend key.
2. Set the **GitHub repo secret** `INTERNAL_API_KEY`
   (`github.com/lvl13tech/wallstbots → Settings → Secrets and variables → Actions`) to the **exact same**
   value (watch for trailing spaces/newlines when pasting).
3. Run **Actions → Refresh lvl13.tech → Run workflow**. Open the run → `refresh` job →
   **Run lvl13 refresh** step and confirm it prints `[push:state] OK pushed to backend` (not 403).
4. Reload `https://lvl13.tech/#/fund/bot13` — the Projected Return box should appear and `last_refresh`
   should advance.

> Note: Option A alone restores the pipeline. If both keys end up = the ORIGINAL key, the legacy
> HostGator script (which has that key) can still clobber data. To truly lock it out, both keys must be
> a NEW value the legacy script doesn't have **and** the legacy cron should be removed (see Option C).

### Option B — Backend schema guard (most robust permanent fix; no key coordination needed)
Add a validation in `Backend/main.py` `tracker_push` so the backend **rejects old-format state**,
regardless of which key is used. Sketch:

```python
@app.post("/internal/tracker/push")
async def tracker_push(payload: TrackerPushRequest, _: None = Depends(verify_internal_key)):
    if payload.data_type not in VALID_DATA_TYPES:
        raise HTTPException(400, "Invalid data_type")
    # --- reject legacy/old-engine state for bot13 ---
    if payload.data_type == "state":
        try:
            cs = payload.data["funds"]["bot13"]["current_strategy"] or {}
            if "projected_return" not in cs or "scored_universe" in cs:
                raise HTTPException(422, "Rejected: legacy bot13 schema (missing projected_return)")
        except (KeyError, TypeError):
            raise HTTPException(422, "Rejected: malformed state payload")
    ... existing INSERT ...
```
Deploy via the **"Deploy Backend to Cloud Run"** GitHub Action (it builds from repo source, so the
`main.py` change must be committed and pushed to `origin/master` first).

### Option C — Kill the source (HostGator)
Log into **HostGator cPanel → Cron Jobs** and delete any job running `python … refresh_data.py`.
Since the sites are fully on Cloudflare now, consider **cancelling the HostGator hosting** entirely.
Also rotate the HostGator FTP password — it is stored in plain text in
`Project/config/secrets.json`.

**Recommended:** Option B (durable, key-independent) + Option C (remove the source) + then optionally
finish the key rotation (Option A with a NEW key) for defense in depth.

---

## Loose ends / hygiene
- **Push the local commit:** `WallStBots` has commit `32e2b2d` (legacy-push disable) committed locally
  but **not pushed** (the repo has diverged from origin and `git push` was rejected; a clean
  `git pull --rebase` then `git push` is needed — there is also a lot of unrelated uncommitted
  line-ending churn in the working tree).
- **Secret exposure:** while editing Cloud Run, several secrets were visible in plain text
  (Supabase service-role key, Polygon, Resend, etc.). Rotate these as general hygiene before launch.
- **Scheduled GitHub runs are flaky:** run #25 and #32 (scheduled) failed; manual runs succeed. Worth
  hardening once the key issue is resolved.

## Key references
- Repo: `github.com/lvl13tech/wallstbots` (branch `master`)
- Backend: Cloud Run `wallstbots-backend`, project `lvl13-tracker-496402`, region `us-east1`
- Backend code: `Backend/main.py` (`tracker_push`, `verify_internal_key`, `tracker_read`)
- Engine: `Project/scripts/bot13_engine.py`; per-site refresh: `Project/scripts/refresh_{lvl13,wallstbots,bitbot13}.py`
- Legacy (now disabled) pusher: `Project/scripts/refresh_data.py` (two copies)
- Frontend renderer: `Frontends/lvl13.tech/assets/app.js` → `renderStrategyPanel()`
- Live data API: `…run.app/public/tracker/state?platform=lvl13`
- Helper scripts created this session (repo root): `FIX1-commit-disable-legacy-pusher.bat`,
  `FIX2-find-legacy-scheduled-task.bat`, `scheduled-tasks-dump.txt`
