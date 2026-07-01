# News Section — Code Outline (2026-06-30)

## TL;DR
The News section is **~90% built** — the frontend renders it and the backend serves it —
but the **data pipeline is dead**, so all 3 sites currently show **0 news items**. The fix
is to revive + generalize the news generator and schedule it. This outline maps what exists,
the exact gap, and the target design.

---

## 1. Current state (what's actually there)

| Layer | Status | Detail |
|-------|--------|--------|
| **Frontend render** | ✅ DONE + wired | `assets/app.js`: `STATE.news`, `newsCard()`, home `renderNews` (top 5 + "More news →"), full `renderNewsAll()` page at `#/news-all`. Fetches `GET /public/tracker/news?platform=X` (cache:no-store). Cards show title, source/sector, relative time, category color (`cat-*`). |
| **Backend serve + store** | ✅ DONE | `/public/tracker/news?platform=X` returns `{items, sectors, generated_at}`. Ingest via `/internal/tracker/push` with `data_type:"news"` (key-gated). `VALID_DATA_TYPES` includes `"news"`. |
| **Generator** | ⚠️ ORPHANED / BROKEN | `Project/scripts/refresh_news.py` exists and even has a working `push_to_api(...,"news",...)`, BUT: (a) it is **not called by any workflow**, (b) it writes to a **dead pre-migration path** `public_html/data/news.json`, (c) it is **single-platform** (sector-stock queries only — no AI/quantum, no crypto), (d) push may not tag `platform`. |
| **Live result** | ❌ EMPTY | Backend `/news` returns `items:[]` for all 3 platforms → the News section shows nothing. |

**So this is a revival + generalization job, not a greenfield build.** The hard parts
(render + serve) are done.

---

## 2. The gap (exactly what's missing)

1. **Nothing runs the generator** → backend news is empty.
2. **Single-platform** → needs 3 query sets: sector stocks (wallstbots), AI/Quantum
   (aistocks), crypto (bitbot13).
3. **Push must be per-platform** → `/internal/tracker/push` needs `platform` in the body so
   each site gets its own relevant feed.
4. **Dead HostGator path** → remove; backend is the only source now (matches the rest of
   the platform post-migration).

---

## 3. Target architecture

```
NewsAPI.org  ──►  refresh_news.py (per platform)  ──►  POST /internal/tracker/push
   (server-side,        - query set per platform        {platform, data_type:"news", data}
    key never in           (sectors / AI+quantum / crypto)        │
    the browser)        - dedupe, filter junk, sort             ▼
                        - tag category + relevance         Supabase (news cache)
                                                                 │
                        GitHub Actions cron ──────────────►      ▼
                        (own workflow OR appended            GET /public/tracker/news?platform=X
                         to each refresh workflow)                │
                                                                  ▼
                                                     app.js renderNews / renderNewsAll
                                                     (already built)
```

Key principle (same as the rest of the platform): **the API key lives only server-side
(secrets.json / GitHub secret), never reaches the browser.** Sites read the pre-fetched
`/news` cache.

---

## 4. Data contract (keep the shape the frontend already expects)

Payload pushed per platform (`data` field of the tracker push):
```json
{
  "items": [
    {
      "title":        "…",            // headline, cleaned (strip " - Source" suffix)
      "source":       "Reuters",      // outlet name
      "sector":       "Semiconductors", // or category tag: "AI", "Quantum", "Crypto", sector
      "category":     "ai",           // NEW: drives cat-* color class in newsCard
      "published_at": "2026-06-30T…", // ISO; frontend relTime() renders "3h ago"
      "url":          "https://…",    // article link
      "tickers":      ["NVDA","AMD"]  // NEW (optional): symbols this story is about
    }
  ],
  "sectors":      ["Semiconductors", "AI", …],  // filter chips on /news-all
  "generated_at": "2026-06-30T…"
}
```
`newsCard()` already reads `title, source|sector, published_at, url, category(cat-*)`.
Adding `category` + `tickers` is additive — no frontend rewrite needed, just richer cards.

---

## 5. Per-platform news config (the valuable part)

Each site should show news **relevant to what its bots actually trade** — this is the whole
point of a per-platform feed.

- **wallstbots** (55 sector stocks): existing `SECTOR_QUERIES` (Semiconductors, Energy,
  Financials, Healthcare, etc.) + "hottest IPOs since 2024".
- **aistocks** (50 AI/Quantum stocks): queries like "artificial intelligence stocks",
  "quantum computing", "AI chips", "data center", + the actual tickers in its universe.
- **bitbot13** (50 crypto): "bitcoin", "ethereum", "crypto regulation", "altcoin", + the
  coin symbols in its universe.

**Relevance boost (optional, high value):** cross-reference each headline against the
platform's UNIVERSE symbols/company names; tag matches with `tickers[]` and sort
universe-relevant stories first. Turns a generic feed into "news about YOUR bots' holdings."

---

## 6. Scheduling
NewsAPI free tier = 100 req/day; each run uses ~6–10. Options:
- **A (simplest):** one new GitHub Actions workflow `refresh-news.yml` on a cron (e.g. every
  3–4 hours) that runs `refresh_news.py --platform X` for all 3 and pushes each. ~60 req/day.
- **B:** append a news step to each existing refresh workflow (gated to run only a few times
  a day via the same backend-marker trick used for emails, to respect the 100/day cap).

Recommend **A** — isolated, easy to reason about, doesn't bloat the trading refreshes.

---

## 7. Security + integrity (reuse existing patterns)
- API key: `newsapi_key` from `secrets.json` (local) / GitHub secret (Actions). Never in
  frontend. ✅ already the design.
- Push auth: `/internal/tracker/push` is key-gated. ✅
- Junk filter: `_is_excluded()` already drops spam/PR-wire sources — extend the blocklist.
- Dedupe: by title prefix (already implemented).
- **No effect on the trading engines or the race** — news is display-only, fully isolated.

---

## 8. Build steps (when we implement)
1. Rewrite `refresh_news.py`: add `--platform {wallstbots,aistocks,bitbot13}`, three query
   sets, tag `category` + `tickers`, push per-platform to the backend, **drop the dead
   HostGator file write**.
2. (Optional) universe-relevance tagging + sort.
3. Add `.github/workflows/refresh-news.yml` (cron, 3 platforms, uses RESEND-style secrets:
   `NEWSAPI_KEY`, `INTERNAL_API_KEY`, `BACKEND_URL`).
4. Confirm `/public/tracker/news?platform=X` now returns items; hard-refresh a site → News
   section populates (frontend already renders).
5. (Optional) enrich `newsCard` with category color + ticker chips (small, additive).
6. Add news checks to `audit_integrity.py` (news fresh within N hours, items > 0, no dead
   URLs) so a stale feed is caught automatically.

---

## 9. Open decisions for the owner
- **Cadence:** every 3–4h, or just AM + midday? (cost vs freshness)
- **Relevance:** generic sector/topic feed, OR universe-matched "news about your holdings"?
- **Depth:** headlines-only (current), or add a short AI summary per story (extra cost)?
- **Placement:** keep on home + `/news-all`, or also surface per-fund/per-symbol news on the
  bot pages?
