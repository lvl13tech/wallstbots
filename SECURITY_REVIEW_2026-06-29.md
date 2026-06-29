# WallStBots Security Review — 2026-06-29

**Trigger:** 3 unknown accounts (`yasuo11111@proton.me`, `renavit147@fanchatu.com`,
`sovevak441@herojp.com`) found receiving member emails. **Read-only audit** of the
backend (68 endpoints) + auth/signup surface.

## Bottom line
**No breach.** No evidence anyone accessed admin, the database, secrets, or
infrastructure. The unknown accounts are **automated spam/bot signups** through the
open free-registration form — the classic signature: disposable/anonymous email
domains (`herojp.com`, `fanchatu.com`, `proton.me`) + an unprotected public signup
endpoint. This is form abuse, not intrusion.

## Endpoint auth audit — result
All 68 endpoints reviewed. Every admin/internal endpoint is correctly protected by
either an admin JWT (`require_admin`) or the `X-Internal-Key` header. Specifically
cleared (initially looked "open", actually protected):
- `/webmaster/set-owner` → requires `X-Internal-Key`. **Not exposed.**
- `/admin/email-subscribers`, all `/internal/*`, `/admin/*` → protected. **OK.**
- `POST /portfolio/{id}/comments` → requires login. **OK.**

Appropriately public (by design, no change needed): `/auth/login`, `/auth/refresh`,
`/auth/password-reset`, `/stripe/webhook`, `/public/tracker/*`, `/leaderboard`,
`/portfolio/{id}/public`, `/portfolio/{id}/comments` (GET), `/health`, `/health/db`.

## Findings (abuse vectors, ranked) — none are a breach
1. **Open signup, no bot protection** *(the entry point used)* — `/auth/signup`,
   `/auth/signup-free`, `/auth/signup-with-admin-code` have no captcha and no rate
   limit. Bots can mass-create accounts.
   - **Already mitigated (shipped 2026-06-29):** member emails now require a
     **confirmed** email address, so unconfirmed bot accounts receive nothing.
   - **Remaining fix:** add a captcha (Cloudflare Turnstile / hCaptcha) to the signup
     form + per-IP rate limiting so bots can't create the rows at all.
2. **No rate limiting anywhere in the backend** *(systemic)* — confirmed zero
   rate-limit code. This is the common root behind: signup spam, `/support/ticket`
   spam, and brute-forcing `/promo-codes/validate` & `/subscriptions/validate-referral`
   (an attacker can guess codes with unlimited tries).
   - **Fix:** add app-level rate limiting (e.g. `slowapi`) on the public POST/validate
     endpoints, keyed by IP, with sane per-minute caps. Cloudflare in front of the API
     can also enforce this at the edge.
3. **`POST /support/ticket` is fully public** — no auth, no rate limit → spammable
   (junk tickets / email amplification if it notifies you per ticket).
   - **Fix:** captcha or rate limit; optionally require login.
4. **Public code validators leak validity** — `/promo-codes/validate` and
   `/subscriptions/validate-referral` confirm whether a code is valid with no throttle.
   - **Fix:** rate-limit; consider generic responses so they can't be enumerated.
5. **Account deletion was missing** *(operational gap, now fixed)* — there was no way
   to remove a user. **Shipped 2026-06-29:** admin-only `DELETE /admin/users/{id}`
   (full data + auth-row removal, refuses admins/paid accounts).

## What was shipped this session (security)
- `DELETE /admin/users/{id}` — admin hard-delete of a user + all their data + Supabase
  auth row.
- Email-confirmation gate on the member-email subscriber list (blocks unconfirmed
  bot/spam signups from receiving mail).
- `remove_spam_users.py` — one-shot cleanup of the 3 known spam accounts.

## Recommended next steps (in priority order)
1. **Run the cleanup** — delete the 3 spam accounts (`REMOVE-spam-users` bat).
2. **Add captcha to the signup form** (Turnstile is free, ~1 frontend snippet + 1
   backend verify call) — the single highest-leverage fix; kills automated signups.
3. **Add backend rate limiting** (`slowapi`) on all public POST/validate endpoints.
4. **Rate-limit / captcha `/support/ticket`.**
5. **Optional:** alert (email to you) when a NEW account confirms, so you see real
   growth and spot anomalies early.

## Notes
- Secrets (`SUPABASE_SERVICE_ROLE_KEY`, `INTERNAL_API_KEY`, `RESEND_API_KEY`) live in
  env / GitHub Secrets, not in code — good. Keep them out of committed files.
- The account-takeover surface (login, password reset) uses Supabase Auth — standard,
  not custom; lower risk. No custom password handling in this codebase.
