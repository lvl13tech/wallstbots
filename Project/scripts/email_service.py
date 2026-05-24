"""
email_service.py
----------------
Resend-based email service for WallStBots / BitBot13 / Level XIII.
Sends daily signals, Bot13 trade alerts, weekly picks, monthly picks.

Requires env var: RESEND_API_KEY
Sends from: info@lvl13.tech (verified Resend domain)
"""

import os
import json
import requests
from datetime import datetime, date
from typing import Optional

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL     = "Wall St. Bots <info@lvl13.tech>"
API_URL        = "https://api.resend.com/emails"

SITE_NAMES = {
    "wallstbots": "Wall St. Bots",
    "bitbot13":   "BitBot13",
    "lvl13":      "Level XIII Tech",
}
SITE_URLS = {
    "wallstbots": "https://wallstbots.tech",
    "bitbot13":   "https://bitbot13.tech",
    "lvl13":      "https://lvl13.tech",
}
ASSET_LABEL = {
    "wallstbots": "stocks",
    "bitbot13":   "coins",
    "lvl13":      "stocks",
}


# ── Resend sender ──────────────────────────────────────────────────────────────
def send_email(to: str, subject: str, html: str) -> bool:
    """Send a single email via Resend. Returns True on success."""
    if not RESEND_API_KEY:
        print("[email] ERROR: RESEND_API_KEY not set")
        return False
    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={"from": FROM_EMAIL, "to": [to], "subject": subject, "html": html},
        timeout=15,
    )
    if resp.status_code in (200, 201):
        return True
    print(f"[email] FAILED {to}: {resp.status_code} {resp.text[:200]}")
    return False


def send_batch(recipients: list[dict], subject: str, html_fn) -> dict:
    """
    Send to a list of recipients using a per-recipient HTML builder.
    recipients: list of dicts with at least {"email": str}
    html_fn: callable(recipient_dict) -> html string
    Returns {"sent": n, "failed": n}
    """
    sent = failed = 0
    for r in recipients:
        try:
            html = html_fn(r)
            ok = send_email(r["email"], subject, html)
            if ok:
                sent += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[email] Exception for {r.get('email')}: {e}")
            failed += 1
    return {"sent": sent, "failed": failed}


# ── Shared HTML shell ──────────────────────────────────────────────────────────
def _wrap(platform: str, preheader: str, body_html: str) -> str:
    site_name = SITE_NAMES.get(platform, "WallStBots")
    site_url  = SITE_URLS.get(platform, "https://wallstbots.tech")
    year      = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{site_name}</title>
</head>
<body style="margin:0;padding:0;background:#06080d;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#e6edf3;">
<span style="display:none;max-height:0;overflow:hidden;">{preheader}</span>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#06080d;padding:24px 0;">
  <tr><td align="center">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

      <!-- HEADER -->
      <tr><td style="background:#0d1117;border-bottom:1px solid #1e2633;padding:20px 28px;border-radius:12px 12px 0 0;">
        <a href="{site_url}" style="text-decoration:none;font-size:1.2rem;font-weight:700;color:#e6edf3;letter-spacing:-0.5px;">
          {_logo_html(platform)}
        </a>
      </td></tr>

      <!-- BODY -->
      <tr><td style="background:#0d1117;padding:28px;">
        {body_html}
      </td></tr>

      <!-- FOOTER -->
      <tr><td style="background:#0a0e16;border-top:1px solid #1e2633;padding:20px 28px;border-radius:0 0 12px 12px;text-align:center;">
        <p style="font-size:0.75rem;color:#7d8590;margin:0 0 8px;">
          You're receiving this because you signed up for {site_name}.
        </p>
        <p style="font-size:0.75rem;color:#7d8590;margin:0;">
          <a href="{site_url}/dashboard.html" style="color:#00d4ff;text-decoration:none;">Dashboard</a>
          &nbsp;·&nbsp;
          <a href="{site_url}/dashboard.html#email-prefs" style="color:#7d8590;text-decoration:none;">Email preferences</a>
          &nbsp;·&nbsp;
          <span style="color:#555;">&copy; {year} {site_name}</span>
        </p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


def _logo_html(platform: str) -> str:
    logos = {
        "wallstbots": "Wall St. <span style='color:#00d4ff;'>Bots</span>",
        "bitbot13":   "Bit<span style='color:#00d4ff;'>Bot13</span>",
        "lvl13":      "Level XIII <span style='color:#00d4ff;'>Tech</span>",
    }
    return logos.get(platform, "WallStBots")


def _signal_badge(action: str) -> str:
    colors = {
        "STRONG BUY":  ("#00d4ff", "#003d47"),
        "BUY":         ("#34d399", "#064e3b"),
        "HOLD":        ("#7d8590", "#1e2633"),
        "SELL":        ("#f97316", "#431407"),
        "STRONG SELL": ("#f85149", "#450a0a"),
    }
    fg, bg = colors.get(action.upper(), ("#7d8590", "#1e2633"))
    return (f'<span style="background:{bg};color:{fg};border:1px solid {fg}33;'
            f'border-radius:4px;padding:2px 8px;font-size:0.72rem;font-weight:700;'
            f'letter-spacing:0.5px;white-space:nowrap;">{action}</span>')


def _pick_row(symbol: str, weight_pct: str, rationale: str) -> str:
    return f"""
<tr>
  <td style="padding:10px 14px;border-bottom:1px solid #1e2633;font-weight:700;font-size:0.9rem;white-space:nowrap;">{symbol}</td>
  <td style="padding:10px 14px;border-bottom:1px solid #1e2633;color:#00d4ff;font-weight:600;text-align:right;white-space:nowrap;">{weight_pct}</td>
  <td style="padding:10px 14px;border-bottom:1px solid #1e2633;font-size:0.8rem;color:#7d8590;">{rationale}</td>
</tr>"""


def _signal_row(symbol: str, action: str, reason: str, price: Optional[float] = None) -> str:
    price_str = f"${price:,.2f}" if price else ""
    return f"""
<tr>
  <td style="padding:9px 14px;border-bottom:1px solid #1e2633;font-weight:700;font-size:0.88rem;">{symbol}</td>
  <td style="padding:9px 14px;border-bottom:1px solid #1e2633;text-align:center;">{_signal_badge(action)}</td>
  <td style="padding:9px 14px;border-bottom:1px solid #1e2633;color:#00d4ff;font-size:0.82rem;text-align:right;">{price_str}</td>
  <td style="padding:9px 14px;border-bottom:1px solid #1e2633;font-size:0.78rem;color:#7d8590;">{reason}</td>
</tr>"""


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 1 — Daily Signals
# ═══════════════════════════════════════════════════════════════════
def build_daily_signals_email(
    platform: str,
    site_signals: list[dict],          # from signals.json recommendations
    bot13_strategy: dict,              # from state.json funds.bot13.current_strategy
    leaderboard: list[dict],           # from state.json leaderboards.week
    recipient: dict,                   # {email, first_name, tier, portfolio_signals:[]}
) -> str:
    """
    Daily email: top signals from the site's list + (for paid) personal portfolio signals.
    """
    name       = recipient.get("first_name") or "Trader"
    tier       = recipient.get("tier", "free")
    source     = recipient.get("email_source", "both")  # site | portfolio | both
    asset      = ASSET_LABEL.get(platform, "stocks")
    site_name  = SITE_NAMES[platform]
    site_url   = SITE_URLS[platform]
    today      = date.today().strftime("%B %d, %Y")

    # Bot13 decision line
    b13_decision = bot13_strategy.get("decision", "HOLD")
    b13_rationale = bot13_strategy.get("rationale", "")
    b13_picks = bot13_strategy.get("picks", [])

    b13_color = "#00d4ff" if b13_decision == "TRADE" else "#f97316" if b13_decision == "SELL" else "#7d8590"
    b13_block = f"""
<div style="background:#0a0e16;border:1px solid #1e2633;border-radius:10px;padding:16px 20px;margin-bottom:20px;">
  <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#7d8590;margin-bottom:8px;">BOT13 · TODAY</div>
  <div style="font-size:1.1rem;font-weight:700;color:{b13_color};margin-bottom:6px;">{b13_decision}</div>
  <div style="font-size:0.82rem;color:#adb8c6;line-height:1.6;">{b13_rationale}</div>
</div>"""

    # Top site signals (top 10, exclude HOLD)
    strong_sigs = [s for s in site_signals if s.get("action","").upper() in ("STRONG BUY","BUY","STRONG SELL","SELL")][:10]
    sig_rows = "".join(_signal_row(
        s["symbol"], s["action"], s.get("reason","")[:80], s.get("price")
    ) for s in strong_sigs)

    site_signals_block = ""
    if source in ("site", "both") and sig_rows:
        site_signals_block = f"""
<h3 style="font-size:0.85rem;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#7d8590;margin:24px 0 12px;">
  Today's Top Signals — {site_name}'s {asset.title()} List
</h3>
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:9px 14px;text-align:left;font-size:0.7rem;color:#7d8590;text-transform:uppercase;letter-spacing:0.6px;">Symbol</th>
      <th style="padding:9px 14px;text-align:center;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Signal</th>
      <th style="padding:9px 14px;text-align:right;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Price</th>
      <th style="padding:9px 14px;text-align:left;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Reason</th>
    </tr>
  </thead>
  <tbody>{sig_rows}</tbody>
</table>"""

    # Personal portfolio signals (paid only)
    portfolio_block = ""
    port_signals = recipient.get("portfolio_signals", [])
    if tier != "free" and source in ("portfolio", "both") and port_signals:
        port_rows = "".join(_signal_row(
            s["symbol"], s["action"], s.get("reason","")[:80], s.get("price")
        ) for s in port_signals[:20])
        portfolio_block = f"""
<h3 style="font-size:0.85rem;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#7d8590;margin:28px 0 12px;">
  Your Portfolio Signals
</h3>
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:9px 14px;text-align:left;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Symbol</th>
      <th style="padding:9px 14px;text-align:center;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Signal</th>
      <th style="padding:9px 14px;text-align:right;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Price</th>
      <th style="padding:9px 14px;text-align:left;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Reason</th>
    </tr>
  </thead>
  <tbody>{port_rows}</tbody>
</table>"""

    # Leaderboard mini strip
    lb_cells = ""
    for entry in leaderboard[:5]:
        pct = entry.get("week_pct", 0)
        clr = "#00d4ff" if pct >= 0 else "#f85149"
        lb_cells += f"""
<td style="text-align:center;padding:10px 12px;border-right:1px solid #1e2633;">
  <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;color:#7d8590;">{entry['fund'].upper()}</div>
  <div style="font-size:0.95rem;font-weight:700;color:{clr};margin-top:4px;">{'+' if pct >= 0 else ''}{pct:.1f}%</div>
  <div style="font-size:0.68rem;color:#555;">{entry.get('week_grade','—')}</div>
</td>"""

    body = f"""
<p style="font-size:0.95rem;color:#adb8c6;margin:0 0 20px;">
  Hey {name} — here's your daily update for <strong style="color:#e6edf3;">{today}</strong>.
</p>

{b13_block}

{site_signals_block}

{portfolio_block}

<!-- Leaderboard strip -->
<h3 style="font-size:0.85rem;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#7d8590;margin:28px 0 12px;">
  This Week's Bot Leaderboard
</h3>
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <tr style="background:#141b27;">{lb_cells}</tr>
</table>

<div style="text-align:center;margin-top:28px;">
  <a href="{site_url}/dashboard.html" style="background:#003d47;border:1px solid #00d4ff;color:#00d4ff;border-radius:8px;padding:10px 24px;font-size:0.875rem;font-weight:600;text-decoration:none;display:inline-block;">
    Open My Dashboard →
  </a>
</div>"""

    return _wrap(platform, f"BOT13: {b13_decision} · {len(strong_sigs)} signals today", body)


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 2 — Bot13 Trade Alert
# ═══════════════════════════════════════════════════════════════════
def build_bot13_alert_email(
    platform: str,
    strategy: dict,   # bot13 current_strategy dict
    recipient: dict,
) -> str:
    name     = recipient.get("first_name") or "Trader"
    site_url = SITE_URLS[platform]
    decision = strategy.get("decision", "HOLD")
    rationale = strategy.get("rationale", "")
    picks    = strategy.get("picks", [])
    today    = date.today().strftime("%B %d, %Y")

    if decision == "HOLD":
        action_line = '<span style="color:#7d8590;font-size:1.5rem;font-weight:700;">HOLDING CASH</span>'
        sub = "BOT13 is sitting out today"
    elif decision == "TRADE":
        action_line = '<span style="color:#00d4ff;font-size:1.5rem;font-weight:700;">TRADE ENTERED ↑</span>'
        sub = f"BOT13 entered {len(picks)} position{'s' if len(picks)!=1 else ''}"
    else:
        action_line = f'<span style="color:#f97316;font-size:1.5rem;font-weight:700;">{decision}</span>'
        sub = f"BOT13 action: {decision}"

    picks_rows = ""
    if picks:
        picks_rows = "".join(_pick_row(
            p["symbol"],
            f"{p['weight']*100:.1f}%",
            p.get("rationale", "")[:100]
        ) for p in picks)
        picks_table = f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;margin-top:16px;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:9px 14px;text-align:left;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Symbol</th>
      <th style="padding:9px 14px;text-align:right;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Allocation</th>
      <th style="padding:9px 14px;text-align:left;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Rationale</th>
    </tr>
  </thead>
  <tbody>{picks_rows}</tbody>
</table>"""
    else:
        picks_table = ""

    body = f"""
<p style="font-size:0.9rem;color:#7d8590;margin:0 0 16px;">BOT13 · {today}</p>

<div style="text-align:center;margin-bottom:24px;">
  {action_line}
</div>

<div style="background:#0a0e16;border:1px solid #1e2633;border-radius:10px;padding:16px 20px;margin-bottom:20px;">
  <p style="font-size:0.85rem;color:#adb8c6;line-height:1.7;margin:0;">{rationale}</p>
</div>

{picks_table}

<div style="text-align:center;margin-top:28px;">
  <a href="{site_url}/dashboard.html" style="background:#003d47;border:1px solid #00d4ff;color:#00d4ff;border-radius:8px;padding:10px 24px;font-size:0.875rem;font-weight:600;text-decoration:none;display:inline-block;">
    View Full Dashboard →
  </a>
</div>"""

    return _wrap(platform, sub, body)


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 3 — Weekly Picks (ORACLE)
# ═══════════════════════════════════════════════════════════════════
def build_weekly_email(
    platform: str,
    oracle_strategy: dict,
    leaderboard: list[dict],
    recipient: dict,
) -> str:
    name     = recipient.get("first_name") or "Trader"
    site_url = SITE_URLS[platform]
    week     = oracle_strategy.get("week", str(date.today()))
    decision = oracle_strategy.get("decision", "HOLD")
    rationale = oracle_strategy.get("rationale", "")
    picks    = oracle_strategy.get("picks", [])

    picks_rows = "".join(_pick_row(
        p["symbol"], f"{p['weight']*100:.1f}%", p.get("rationale","")[:120]
    ) for p in picks)

    picks_block = f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:9px 14px;text-align:left;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Symbol</th>
      <th style="padding:9px 14px;text-align:right;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Weight</th>
      <th style="padding:9px 14px;text-align:left;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Thesis</th>
    </tr>
  </thead>
  <tbody>{picks_rows}</tbody>
</table>""" if picks_rows else "<p style='color:#7d8590;font-size:0.85rem;'>No new positions this week — Oracle is in cash.</p>"

    body = f"""
<p style="font-size:0.9rem;color:#7d8590;margin:0 0 4px;">ORACLE — Weekly Picks</p>
<h2 style="font-size:1.3rem;font-weight:700;margin:0 0 20px;">Week of {week}</h2>

<p style="font-size:0.9rem;color:#adb8c6;line-height:1.7;margin:0 0 20px;">{rationale}</p>

<h3 style="font-size:0.85rem;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#7d8590;margin:0 0 12px;">
  This Week's Positions
</h3>

{picks_block}

<div style="text-align:center;margin-top:28px;">
  <a href="{site_url}/dashboard.html" style="background:#003d47;border:1px solid #00d4ff;color:#00d4ff;border-radius:8px;padding:10px 24px;font-size:0.875rem;font-weight:600;text-decoration:none;display:inline-block;">
    Track Performance →
  </a>
</div>"""

    return _wrap(platform, f"Oracle's weekly picks — {len(picks)} positions", body)


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 4 — Monthly Picks (WIZARD)
# ═══════════════════════════════════════════════════════════════════
def build_monthly_email(
    platform: str,
    wizard_strategy: dict,
    leaderboard: list[dict],
    recipient: dict,
) -> str:
    name     = recipient.get("first_name") or "Trader"
    site_url = SITE_URLS[platform]
    rationale = wizard_strategy.get("rationale", "")
    picks    = wizard_strategy.get("picks", [])
    month    = date.today().strftime("%B %Y")

    picks_rows = "".join(_pick_row(
        p["symbol"], f"{p['weight']*100:.1f}%", p.get("rationale","")[:120]
    ) for p in picks)

    picks_block = f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:9px 14px;text-align:left;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Symbol</th>
      <th style="padding:9px 14px;text-align:right;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Weight</th>
      <th style="padding:9px 14px;text-align:left;font-size:0.7rem;color:#7d8590;text-transform:uppercase;">Thesis</th>
    </tr>
  </thead>
  <tbody>{picks_rows}</tbody>
</table>""" if picks_rows else "<p style='color:#7d8590;font-size:0.85rem;'>Wizard is holding current positions this month.</p>"

    body = f"""
<p style="font-size:0.9rem;color:#7d8590;margin:0 0 4px;">WIZARD — Monthly Portfolio</p>
<h2 style="font-size:1.3rem;font-weight:700;margin:0 0 20px;">{month} Picks</h2>

<p style="font-size:0.9rem;color:#adb8c6;line-height:1.7;margin:0 0 20px;">{rationale}</p>

<h3 style="font-size:0.85rem;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#7d8590;margin:0 0 12px;">
  This Month's Positions
</h3>

{picks_block}

<div style="text-align:center;margin-top:28px;">
  <a href="{site_url}/dashboard.html" style="background:#003d47;border:1px solid #00d4ff;color:#00d4ff;border-radius:8px;padding:10px 24px;font-size:0.875rem;font-weight:600;text-decoration:none;display:inline-block;">
    View Full Report →
  </a>
</div>"""

    return _wrap(platform, f"Wizard's monthly picks for {month}", body)
