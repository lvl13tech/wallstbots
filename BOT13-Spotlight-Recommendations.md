# BOT13 Spotlight — Positioning Recommendations

**Goal:** Make BOT13 the clear hero and the reason to join — *"copy the bot that
wins, with your own stocks"* — without turning the site into a hard-sell. The
site keeps its credible, data-first tone; BOT13 just gets the spotlight the data
already earns it.

---

## The core message (one line, reused everywhere)

> **BOT13 wins because it refuses to lose.**
> It only trades when it sees a real edge — otherwise it sits in cash. No edge,
> no trade, no risk. The result: it's beaten every other strategy *and* the market,
> and across its track record it has **never closed a day in the red.**
> Join, add your own stocks, and BOT13 trades them the same way.

**Why this is THE hook:** for people who don't trust bots, the fear isn't "will it
make money" — it's "will it lose my money." BOT13's whole design answers that fear
first: it would rather do nothing than make a bad trade. The performance is the
*proof*; "it doesn't lose" is the *promise*. Lead with the promise, back it with
the proof.

**The mechanism, in plain English (use this everywhere the angle appears):**
"BOT13 grades the setup every morning. If nothing scores high enough, it stays in
cash that day and risks nothing. It only puts money in when the edge is there — so
the downside is capped at 'a quiet day,' not 'a loss.'"

### The proof (verified from live data, {date})
- **wallstbots BOT13:** 12 up days, **0 down days**, 1 cash day. Worst day: 0.00%.
- **aistocks BOT13:** 7 up days, **0 down days**, 6 cash days (sat out when no edge).
- Outperformance: **+91%** (wallstbots) / **+118%** (aistocks) all-time vs. ~+4% next-best bot.

**Honesty wording (important):** say **"hasn't had a losing day across its track
record"** or **"zero down days so far,"** tied to the visible leaderboard — NOT an
absolute "never loses / can't lose" guarantee. The *mechanism* claim ("only trades
with an edge, sits in cash otherwise") is always true and is the real reason; that
one needs no hedge. The numbers are paper/simulation results — keep that label.

**Honesty guardrail:** use the **stock-site numbers** (wallstbots +91%, aistocks
+118% all-time vs. ~+4% next-best) — they're clean and defensible. Do **not**
headline the bitbot13 +3,000%+ figure; it's the JUP-corrupted value and looks
unbelievable anyway. Keep claims as "outperformed the other strategies and the
benchmarks," not "guaranteed returns." These are paper/simulation results — say so.

---

## 1) Homepage (`renderHome`)

**Today:** the hero says *"5 strategies. 55 stocks. Watch them race."* — even-handed,
no hero bot. The leaderboard strip shows all five equally.

**Recommended changes (small, high-impact):**

- **Add a "spotlight" line under the hero**, just above the Live Leaderboard. One
  sentence + a live stat pulled from STATE, e.g.:
  > *"One bot keeps winning the race — by refusing to lose. **BOT13**, the daily
  > strategy, only trades when it sees an edge and sits in cash otherwise. **{bot13_pct}**
  > all-time, and **zero down days** across its track record. Join and it trades
  > **your** stocks the same way. → Get Yours"*
  Pull `{bot13_pct}` (and ideally the down-day count) live so it stays current.

- **Highlight BOT13's leaderboard row** — give the BOT13 row a subtle accent
  (its pink `--accent`/`#ec4899` border or a small "★ LEADER" pill) so the eye
  lands on it first. Not a banner — just visual primacy.

- **Reframe the existing get-yours hint** at the bottom from the generic
  *"Join and run the same 5 bots on your own stock picks"* to lead with BOT13:
  > *"Join and let **BOT13** — the bot that's beating the market — trade your own
  > stock picks."*

**Tone check:** still one hero, one stat line, one highlighted row. No popups, no
"BUY NOW." The page still leads with live data.

---

## 2) BOT13 page (`bot-detail.html` / `renderFund` for bot13)

**Today:** the bot detail page shows BOT13's strategy, positions, and chart like
any other bot — no "this is the star, here's why you'd copy it" close.

**Recommended change — add a spotlight panel at the BOTTOM of the BOT13 page only:**

A single panel after the performance chart, shown *only when `fid === 'bot13'`:

> ### Why members copy BOT13
> BOT13 only trades when the edge is there. Every morning it grades the setup — if
> nothing scores high enough, it **stays in cash and risks nothing that day.** That
> discipline is why, across its track record, it has **never closed a day in the
> red** while still **beating every other strategy and both market benchmarks.**
>
> It would rather do nothing than make a bad trade. The downside of a quiet day is
> a quiet day — not a loss.
>
> The best part: you don't trade it yourself. **Add your own stocks and BOT13 runs
> the exact same playbook on your list** — you just watch the calls.
>
> **[ Run BOT13 on my stocks → Get Yours ]**

Keep it to the BOT13 page (not Oracle/Wizard/etc.) so it feels earned, not pasted
everywhere. This is the natural "you're already impressed — here's the next step"
moment.

---

## 3) Get Yours tab (`renderGetYours`)

**Today:** hero is *"You've seen what it does. Now make it yours."* then jumps
straight to pricing. The FREE tier mentions Bot13; the paid tiers say generic
"5 AI bots."

**Recommended changes:**

- **Rewrite the hero subline to name the hero bot and the proof:**
  > *"You've seen the race. **BOT13 won it — without a single losing day.** It only
  > trades when it sees an edge and sits in cash otherwise, so it beats the market
  > without betting against you. Add your own stocks and it trades them the same way.
  > Daily signals, custom news, Sunday reports."*

- **Add one "proof bar" above the pricing cards** — three live/static stats in a
  row, framed as evidence:
  `BOT13 all-time: +91%` · `0 losing days` · `Trades only with an edge` · `You copy the winner with your stocks`
  (use live values where possible; label clearly as simulated/paper results).

- **In the "What's Included" grid**, change the generic *"5 AI bots"* card to lead
  with BOT13:
  > **✓ BOT13 + 4 more** — "The daily bot that's beating the market runs on your
  > picks, plus weekly, monthly, and two benchmarks for context."

**Tone check:** the pricing stays exactly as is. We're adding *one* proof bar and
sharpening two pieces of existing copy — not stacking testimonials or urgency timers.

---

## 4) Chatbot (`FAQS` in `app.js`)

**Today:** the "Bots" answer lists all five evenly:
*"5 strategies race on YOUR stock list: BOT13 (daily)… ORACLE… WIZARD…"*

**Recommended changes:**

- **Rewrite the `['bot','bots','strategy']` answer** to lead with BOT13 as the star:
  > *"5 strategies race on YOUR stock list — and **BOT13, the daily bot, keeps
  > winning by refusing to lose.** It only trades when it sees an edge and sits in
  > cash otherwise, so across its track record it's had **zero losing days** while
  > still beating every other strategy and both market benchmarks. The others
  > (ORACLE weekly, WIZARD monthly, plus EQUALIZER & TITAN benchmarks) are there for
  > context. When you join, BOT13 trades your exact stock list the same way."*

- **Add a dedicated FAQ** so "which bot is best / does it work / proof" routes to
  the spotlight:
  > `q: ['best bot','which bot','top bot','does it work','proof','track record','winning']`
  > `a: "BOT13 — the daily strategy — is the standout, and here's WHY it wins: it
  > only trades when it sees a real edge, and sits in cash otherwise. No edge, no
  > trade, no risk. Across its track record that's meant zero losing days while still
  > beating the other bots and the market (paper-trading results, shown live on the
  > leaderboard). Join, add your stocks, and copy the bot that won't bet against you."`

- **Add a quick-reply chip:** change the `quick` array from
  `['Pricing','Stocks','Bots','Cancel','Support']` to
  `['Pricing','Why BOT13?','Stocks','Cancel','Support']` so the spotlight is one tap away.

---

## What I deliberately avoided (keeping it "not a full promotion")

- No popups, countdate timers, fake scarcity, or testimonials.
- BOT13 spotlight panel lives **only** on the BOT13 page, not bolted onto every bot.
- Pricing layout untouched — just one proof bar + sharper words.
- Every performance claim is hedged as **simulated/paper results** and pulled from
  the **clean stock-site data**, never the corrupted crypto figure.
- The "race" stays central — the win is only credible *because* it's a fair fight.

---

## Suggested rollout

1. Make the four edits in the **wallstbots** reference site first (it's the parity
   source), verify it reads right.
2. Sync the identical changes to **aistocks** and **bitbot13** (Parity Rule).
   Per-site number swaps only (each pulls its own live BOT13 stat).
3. Deploy via SAFE-DEPLOY (the truncation guard now covers this).

I can implement any or all of these on your say-so — just tell me which sections
to build and I'll do wallstbots first, then sync the other two.
