"""
email_service.py
----------------
Resend-based email service for WallStBots / BitBot13 / Level XIII.
Sends daily signals, Bot13 trade alerts, weekly picks, monthly picks.

Design matches the site exactly:
  bg=#06080d  panel=#0d1117  panel2=#141b27  border=#1e2633
  text=#e6edf3  muted=#7d8590  blue=#00d4ff  green=#3fb950
  red=#f85149  pink=#ec4899  purple=#a855f7  emerald=#10b981
  orange=#ff8c00  gold=#facc15

Requires env var: RESEND_API_KEY
Sends from: info@lvl13.tech (verified Resend domain)
"""

import os
import requests
from datetime import datetime, date
from typing import Optional

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL     = "Wall St. Bots <info@lvl13.tech>"
API_URL        = "https://api.resend.com/emails"

# ── Site config ────────────────────────────────────────────────────────────────
SITE_NAMES = {
    "wallstbots": "Wall St. Bots",
    "bitbot13":   "BitBot13",
    "lvl13":      "Level XIII",
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

# ── Bot colours (matches style.css fund-icon classes) ─────────────────────────
BOT_COLORS = {
    "bot13":     {"bg": "#ec4899", "border": "#ec4899", "grad_start": "rgba(236,72,153,0.12)", "grad_end": "rgba(236,72,153,0.02)", "label": "BOT13",     "abbr": "B13"},
    "oracle":    {"bg": "#a855f7", "border": "#a855f7", "grad_start": "rgba(168,85,247,0.12)",  "grad_end": "rgba(168,85,247,0.02)",  "label": "ORACLE",    "abbr": "OR"},
    "wizard":    {"bg": "#10b981", "border": "#10b981", "grad_start": "rgba(16,185,129,0.12)",  "grad_end": "rgba(16,185,129,0.02)",  "label": "WIZARD",    "abbr": "WZ"},
    "equalizer": {"bg": "#00d4ff", "border": "#00d4ff", "grad_start": "rgba(0,212,255,0.12)",   "grad_end": "rgba(0,212,255,0.02)",   "label": "EQUALIZER", "abbr": "EQ"},
    "titan":     {"bg": "#ff8c00", "border": "#ff8c00", "grad_start": "rgba(255,140,0,0.12)",   "grad_end": "rgba(255,140,0,0.02)",   "label": "TITAN",     "abbr": "TI"},
}

# ── Signal pill styling (matches .signal-* classes) ───────────────────────────
SIGNAL_STYLES = {
    "STRONG BUY":  {"bg": "rgba(63,185,80,0.18)",  "color": "#4ade80", "border": "#3fb950"},
    "BUY":         {"bg": "rgba(63,185,80,0.08)",  "color": "#86efac", "border": "rgba(63,185,80,0.5)"},
    "HOLD":        {"bg": "rgba(125,133,144,0.15)","color": "#d1d5db", "border": "#4b5563"},
    "SELL":        {"bg": "rgba(248,81,73,0.10)",  "color": "#fca5a5", "border": "rgba(248,81,73,0.5)"},
    "STRONG SELL": {"bg": "rgba(248,81,73,0.20)",  "color": "#fb7185", "border": "#f85149"},
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
    html_fn: callable(recipient_dict) -> html string
    Returns {"sent": n, "failed": n}
    """
    sent = failed = 0
    for r in recipients:
        try:
            html = html_fn(r)
            ok = send_email(r["email"], subject, html)
            sent += 1 if ok else 0
            failed += 0 if ok else 1
        except Exception as e:
            print(f"[email] Exception for {r.get('email')}: {e}")
            failed += 1
    return {"sent": sent, "failed": failed}


# ── HTML helpers ───────────────────────────────────────────────────────────────
def _logo_html(platform: str) -> str:
    logos = {
        "wallstbots": "Wall St. <span style='color:#00d4ff;'>Bots</span>",
        "bitbot13":   "Bit<span style='color:#00d4ff;'>Bot13</span>",
        "lvl13":      "Level <span style='color:#00d4ff;'>XIII</span>",
    }
    return logos.get(platform, "WallStBots")


def _signal_pill(action: str) -> str:
    """Render a signal pill that matches the .signal-* classes exactly."""
    s = SIGNAL_STYLES.get(action.upper(), SIGNAL_STYLES["HOLD"])
    return (
        f'<span style="display:inline-block;padding:3px 9px;border-radius:999px;'
        f'background:{s["bg"]};color:{s["color"]};border:1px solid {s["border"]};'
        f'font-size:9px;font-weight:800;letter-spacing:0.5px;white-space:nowrap;'
        f'text-transform:uppercase;">{action.upper()}</span>'
    )


def _fund_icon(bot_key: str) -> str:
    """Render a coloured fund icon square matching .fund-icon classes."""
    c = BOT_COLORS.get(bot_key.lower(), BOT_COLORS["bot13"])
    return (
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:28px;height:28px;border-radius:7px;background:{c["bg"]};'
        f'font-weight:800;font-size:11px;color:#06080d;flex-shrink:0;">'
        f'{c["abbr"]}</span>'
    )


def _strategy_card(bot_key: str, label: str, decision: str, rationale: str, extra_html: str = "") -> str:
    """Render a strategy panel matching .strategy-panel.{bot} with gradient border."""
    c = BOT_COLORS.get(bot_key.lower(), BOT_COLORS["bot13"])
    decision_color = "#00d4ff" if decision == "TRADE" else "#f85149" if decision in ("SELL","STRONG SELL") else c["bg"]
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {c['border']};border-radius:14px;overflow:hidden;margin-bottom:20px;">
  <tr>
    <td style="background:linear-gradient(135deg,{c['grad_start']},{c['grad_end']});padding:18px 20px;">
      <!-- label row -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;">
        <tr>
          <td>{_fund_icon(bot_key)}</td>
          <td style="padding-left:10px;">
            <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1px;color:{c['bg']};line-height:1;">{label}</div>
            <div style="font-size:18px;font-weight:800;color:{decision_color};margin-top:4px;letter-spacing:-0.3px;">{decision}</div>
          </td>
        </tr>
      </table>
      <!-- rationale -->
      <p style="font-size:13px;color:#adb8c6;line-height:1.65;margin:0 0 0;">{rationale}</p>
      {extra_html}
    </td>
  </tr>
</table>"""


def _signal_row(symbol: str, action: str, reason: str, price: Optional[float] = None) -> str:
    price_str = f"${price:,.2f}" if price else "—"
    return f"""
<tr>
  <td style="padding:9px 12px;border-bottom:1px solid #1e2633;font-weight:800;font-size:14px;color:#e6edf3;white-space:nowrap;">{symbol}</td>
  <td style="padding:9px 12px;border-bottom:1px solid #1e2633;white-space:nowrap;">{_signal_pill(action)}</td>
  <td style="padding:9px 12px;border-bottom:1px solid #1e2633;color:#00d4ff;font-size:12px;font-weight:600;text-align:right;white-space:nowrap;">{price_str}</td>
  <td style="padding:9px 12px;border-bottom:1px solid #1e2633;font-size:11px;color:#7d8590;max-width:220px;">{reason[:90] if reason else ""}</td>
</tr>"""


def _pick_row(symbol: str, weight_pct: str, rationale: str, bot_key: str = "bot13") -> str:
    c = BOT_COLORS.get(bot_key.lower(), BOT_COLORS["bot13"])
    return f"""
<tr>
  <td style="padding:10px 14px;border-bottom:1px solid #1e2633;font-weight:800;font-size:15px;color:#e6edf3;white-space:nowrap;">{symbol}</td>
  <td style="padding:10px 14px;border-bottom:1px solid #1e2633;font-weight:700;font-size:13px;color:{c['bg']};text-align:right;white-space:nowrap;">{weight_pct}</td>
  <td style="padding:10px 14px;border-bottom:1px solid #1e2633;font-size:11px;color:#7d8590;">{rationale[:110] if rationale else ""}</td>
</tr>"""


def _section_label(text: str) -> str:
    """Uppercase section header matching h3 from style.css."""
    return f'<div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:0.7px;color:#7d8590;margin:24px 0 10px;">{text}</div>'


def _cta_button(url: str, text: str) -> str:
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:28px;">
  <tr>
    <td align="center">
      <a href="{url}" style="display:inline-block;background:#003d47;border:1px solid #00d4ff;color:#00d4ff;border-radius:8px;padding:12px 28px;font-size:14px;font-weight:700;text-decoration:none;letter-spacing:0.2px;">{text} →</a>
    </td>
  </tr>
</table>"""


def _eyebrow(text: str, color: str = "#00d4ff") -> str:
    """Styled eyebrow tag matching .hero-eyebrow."""
    return (
        f'<div style="display:inline-block;padding:4px 12px;'
        f'background:rgba(0,212,255,0.10);border:1px solid {color};'
        f'color:{color};border-radius:999px;font-size:10px;font-weight:800;'
        f'letter-spacing:1px;text-transform:uppercase;margin-bottom:14px;">{text}</div>'
    )


# ── Shell wrapper ──────────────────────────────────────────────────────────────
def _wrap(platform: str, preheader: str, body_html: str) -> str:
    site_name = SITE_NAMES.get(platform, "WallStBots")
    site_url  = SITE_URLS.get(platform, "https://wallstbots.tech")
    year      = datetime.now().year

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="dark"/>
<title>{site_name}</title>
</head>
<body style="margin:0;padding:0;background:#06080d;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,system-ui,sans-serif;color:#e6edf3;-webkit-font-smoothing:antialiased;">

<!-- preheader -->
<span style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</span>

<table width="100%" cellpadding="0" cellspacing="0" style="background:#06080d;padding:28px 0 48px;">
  <tr><td align="center" style="padding:0 16px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

      <!-- ── HEADER ── -->
      <tr>
        <td style="background:#0d1117;border:1px solid #1e2633;border-bottom:2px solid #00d4ff;padding:18px 24px;border-radius:12px 12px 0 0;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <a href="{site_url}" style="text-decoration:none;font-size:20px;font-weight:800;color:#e6edf3;letter-spacing:-0.5px;">
                  {_logo_html(platform)}
                </a>
                <div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#7d8590;margin-top:3px;">AI-Powered Trading Signals</div>
              </td>
              <td align="right">
                <a href="{site_url}/dashboard.html" style="display:inline-block;background:#003d47;border:1px solid #00d4ff;color:#00d4ff;border-radius:6px;padding:7px 14px;font-size:11px;font-weight:700;text-decoration:none;white-space:nowrap;">Dashboard</a>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ── BODY ── -->
      <tr>
        <td style="background:#0d1117;border-left:1px solid #1e2633;border-right:1px solid #1e2633;padding:28px 24px;">
          {body_html}
        </td>
      </tr>

      <!-- ── FOOTER ── -->
      <tr>
        <td style="background:#0a0e16;border:1px solid #1e2633;border-top:none;padding:20px 24px;border-radius:0 0 12px 12px;text-align:center;">
          <p style="font-size:11px;color:#7d8590;margin:0 0 8px;">
            You're receiving this because you're subscribed to {site_name}.
          </p>
          <p style="font-size:11px;margin:0;">
            <a href="{site_url}/dashboard.html" style="color:#00d4ff;text-decoration:none;">Dashboard</a>
            &nbsp;<span style="color:#1e2633;">·</span>&nbsp;
            <a href="{site_url}/dashboard.html#email-prefs" style="color:#7d8590;text-decoration:none;">Email Preferences</a>
            &nbsp;<span style="color:#1e2633;">·</span>&nbsp;
            <span style="color:#4b5563;">&copy; {year} {site_name}</span>
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>

</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 1 — Daily Signals
# ═══════════════════════════════════════════════════════════════════
def build_daily_signals_email(
    platform: str,
    site_signals: list[dict],
    bot13_strategy: dict,
    leaderboard: list[dict],
    recipient: dict,
) -> str:
    name      = recipient.get("first_name") or "Trader"
    tier      = recipient.get("tier", "free")
    source    = recipient.get("email_source", "both")
    asset     = ASSET_LABEL.get(platform, "stocks")
    site_name = SITE_NAMES[platform]
    site_url  = SITE_URLS[platform]
    today_str = date.today().strftime("%B %d, %Y")

    b13_decision  = bot13_strategy.get("decision", "HOLD")
    b13_rationale = bot13_strategy.get("rationale", "BOT13 is holding cash today.")
    b13_picks     = bot13_strategy.get("picks", [])

    # ── Greeting ──────────────────────────────────────────────────
    greeting = f"""
<p style="font-size:15px;color:#adb8c6;margin:0 0 22px;line-height:1.6;">
  Hey <strong style="color:#e6edf3;">{name}</strong> — here's your daily update for <strong style="color:#e6edf3;">{today_str}</strong>.
</p>"""

    # ── BOT13 strategy card ────────────────────────────────────────
    picks_extra = ""
    if b13_picks and b13_decision == "TRADE":
        picks_rows = "".join(_pick_row(p["symbol"], f"{p['weight']*100:.0f}%", p.get("rationale",""), "bot13") for p in b13_picks[:6])
        picks_extra = f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;margin-top:14px;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:8px 14px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Symbol</th>
      <th style="padding:8px 14px;text-align:right;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Alloc.</th>
      <th style="padding:8px 14px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Thesis</th>
    </tr>
  </thead>
  <tbody>{picks_rows}</tbody>
</table>"""

    bot13_block = _strategy_card("bot13", "BOT13 · TODAY", b13_decision, b13_rationale, picks_extra)

    # ── Top signals table ──────────────────────────────────────────
    actionable = [s for s in site_signals if s.get("action","").upper() in ("STRONG BUY","BUY","STRONG SELL","SELL")][:10]
    signals_block = ""
    if source in ("site", "both") and actionable:
        sig_rows = "".join(_signal_row(s["symbol"], s["action"], s.get("reason",""), s.get("price")) for s in actionable)
        signals_block = f"""
{_section_label(f"Today's Top Signals — {asset.title()}s")}
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:8px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Ticker</th>
      <th style="padding:8px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Signal</th>
      <th style="padding:8px 12px;text-align:right;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Price</th>
      <th style="padding:8px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Reason</th>
    </tr>
  </thead>
  <tbody>{sig_rows}</tbody>
</table>"""

    # ── Personal portfolio signals (paid only) ─────────────────────
    portfolio_block = ""
    port_signals = recipient.get("portfolio_signals", [])
    if tier != "free" and source in ("portfolio", "both") and port_signals:
        port_rows = "".join(_signal_row(s["symbol"], s["action"], s.get("reason",""), s.get("price")) for s in port_signals[:15])
        portfolio_block = f"""
{_section_label("Your Portfolio Signals")}
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:8px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Ticker</th>
      <th style="padding:8px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Signal</th>
      <th style="padding:8px 12px;text-align:right;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Price</th>
      <th style="padding:8px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Reason</th>
    </tr>
  </thead>
  <tbody>{port_rows}</tbody>
</table>"""

    # ── Leaderboard strip ──────────────────────────────────────────
    lb_block = ""
    if leaderboard:
        # Map fund names to bot keys
        fund_key_map = {"bot13":"bot13","oracle":"oracle","wizard":"wizard","equalizer":"equalizer","titan":"titan"}
        cols = ""
        for entry in leaderboard[:5]:
            fund   = entry.get("fund","").lower()
            bkey   = fund_key_map.get(fund, "bot13")
            c      = BOT_COLORS.get(bkey, BOT_COLORS["bot13"])
            pct    = entry.get("week_pct", 0)
            pct_color = "#3fb950" if pct >= 0 else "#f85149"
            grade  = entry.get("week_grade", "—")
            cols += f"""
<td style="text-align:center;padding:10px 8px;border-right:1px solid #1e2633;min-width:0;">
  <div style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:7px;background:{c['bg']};font-weight:800;font-size:10px;color:#06080d;margin:0 auto 6px;">{c['abbr']}</div>
  <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#7d8590;letter-spacing:0.5px;">{entry.get('fund','').upper()}</div>
  <div style="font-size:16px;font-weight:800;color:{pct_color};margin-top:3px;font-variant-numeric:tabular-nums;">{'+' if pct >= 0 else ''}{pct:.1f}%</div>
  <div style="font-size:10px;color:#555;margin-top:2px;">{grade}</div>
</td>"""

        lb_block = f"""
{_section_label("This Week's Leaderboard")}
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <tr style="background:#141b27;">{cols}</tr>
</table>"""

    body = greeting + bot13_block + signals_block + portfolio_block + lb_block + _cta_button(f"{site_url}/dashboard.html", "Open My Dashboard")

    preheader = f"BOT13: {b13_decision} · {len(actionable)} signals today · {today_str}"
    return _wrap(platform, preheader, body)


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 2 — Bot13 Trade Alert
# ═══════════════════════════════════════════════════════════════════
def build_bot13_alert_email(
    platform: str,
    strategy: dict,
    recipient: dict,
) -> str:
    name      = recipient.get("first_name") or "Trader"
    site_url  = SITE_URLS[platform]
    decision  = strategy.get("decision", "HOLD")
    rationale = strategy.get("rationale", "")
    picks     = strategy.get("picks", [])
    today_str = date.today().strftime("%B %d, %Y")

    if decision == "TRADE":
        eyebrow_text  = "⚡ TRADE ALERT"
        eyebrow_color = "#ec4899"
        sub_line      = f"BOT13 entered {len(picks)} position{'s' if len(picks) != 1 else ''} today"
        preheader     = f"BOT13 TRADE: {len(picks)} position{'s' if len(picks)!=1 else ''} entered — {today_str}"
    elif decision == "SELL":
        eyebrow_text  = "📉 SELL ALERT"
        eyebrow_color = "#f85149"
        sub_line      = "BOT13 is exiting positions"
        preheader     = f"BOT13 SELL signal — {today_str}"
    else:
        eyebrow_text  = "💤 HOLDING CASH"
        eyebrow_color = "#7d8590"
        sub_line      = "BOT13 is sitting out today"
        preheader     = f"BOT13 is holding cash — {today_str}"

    picks_table = ""
    if picks:
        picks_rows = "".join(_pick_row(p["symbol"], f"{p['weight']*100:.0f}%", p.get("rationale",""), "bot13") for p in picks)
        picks_table = f"""
{_section_label("Positions Entered")}
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:8px 14px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Symbol</th>
      <th style="padding:8px 14px;text-align:right;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Allocation</th>
      <th style="padding:8px 14px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Rationale</th>
    </tr>
  </thead>
  <tbody>{picks_rows}</tbody>
</table>"""

    # eyebrow pill
    eyebrow_html = f'<div style="display:inline-block;padding:4px 12px;background:rgba(236,72,153,0.10);border:1px solid {eyebrow_color};color:{eyebrow_color};border-radius:999px;font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;margin-bottom:16px;">{eyebrow_text}</div>'

    greeting = f"""
<p style="font-size:15px;color:#adb8c6;margin:0 0 18px;line-height:1.6;">
  Hey <strong style="color:#e6edf3;">{name}</strong> — {sub_line}.
</p>"""

    bot13_block = _strategy_card("bot13", f"BOT13 · {today_str}", decision, rationale)

    body = eyebrow_html + greeting + bot13_block + picks_table + _cta_button(f"{site_url}/dashboard.html", "View Full Dashboard")
    return _wrap(platform, preheader, body)


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 3 — Weekly Picks (ORACLE)
# ═══════════════════════════════════════════════════════════════════
def build_weekly_email(
    platform: str,
    oracle_strategy: dict,
    leaderboard: list[dict],
    recipient: dict,
) -> str:
    name      = recipient.get("first_name") or "Trader"
    site_url  = SITE_URLS[platform]
    week      = oracle_strategy.get("week", str(date.today()))
    decision  = oracle_strategy.get("decision", "HOLD")
    rationale = oracle_strategy.get("rationale", "")
    picks     = oracle_strategy.get("picks", [])
    today_str = date.today().strftime("%B %d, %Y")

    eyebrow_html = '<div style="display:inline-block;padding:4px 12px;background:rgba(168,85,247,0.10);border:1px solid #a855f7;color:#a855f7;border-radius:999px;font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;margin-bottom:16px;">📅 WEEKLY PICKS</div>'

    greeting = f"""
<p style="font-size:15px;color:#adb8c6;margin:0 0 18px;line-height:1.6;">
  Hey <strong style="color:#e6edf3;">{name}</strong> — here are Oracle's picks for the week of <strong style="color:#e6edf3;">{week}</strong>.
</p>"""

    oracle_block = _strategy_card("oracle", f"ORACLE · WEEK OF {week.upper()}", decision, rationale)

    picks_table = ""
    if picks:
        picks_rows = "".join(_pick_row(p["symbol"], f"{p['weight']*100:.0f}%", p.get("rationale",""), "oracle") for p in picks)
        picks_table = f"""
{_section_label("This Week's Positions")}
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:8px 14px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Symbol</th>
      <th style="padding:8px 14px;text-align:right;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Weight</th>
      <th style="padding:8px 14px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Thesis</th>
    </tr>
  </thead>
  <tbody>{picks_rows}</tbody>
</table>"""
    else:
        picks_table = '<p style="font-size:13px;color:#7d8590;margin:16px 0 0;">Oracle is holding cash this week — no new positions.</p>'

    body = eyebrow_html + greeting + oracle_block + picks_table + _cta_button(f"{site_url}/dashboard.html", "Track Performance")
    preheader = f"Oracle's weekly picks — {len(picks)} positions · {today_str}"
    return _wrap(platform, preheader, body)


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 4 — Monthly Picks (WIZARD)
# ═══════════════════════════════════════════════════════════════════
def build_monthly_email(
    platform: str,
    wizard_strategy: dict,
    leaderboard: list[dict],
    recipient: dict,
) -> str:
    name      = recipient.get("first_name") or "Trader"
    site_url  = SITE_URLS[platform]
    rationale = wizard_strategy.get("rationale", "")
    picks     = wizard_strategy.get("picks", [])
    month     = date.today().strftime("%B %Y")
    today_str = date.today().strftime("%B %d, %Y")

    eyebrow_html = '<div style="display:inline-block;padding:4px 12px;background:rgba(16,185,129,0.10);border:1px solid #10b981;color:#10b981;border-radius:999px;font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;margin-bottom:16px;">🧙 MONTHLY PORTFOLIO</div>'

    greeting = f"""
<p style="font-size:15px;color:#adb8c6;margin:0 0 18px;line-height:1.6;">
  Hey <strong style="color:#e6edf3;">{name}</strong> — here is Wizard's portfolio strategy for <strong style="color:#e6edf3;">{month}</strong>.
</p>"""

    wizard_block = _strategy_card("wizard", f"WIZARD · {month.upper()}", wizard_strategy.get("decision","HOLD"), rationale)

    picks_table = ""
    if picks:
        picks_rows = "".join(_pick_row(p["symbol"], f"{p['weight']*100:.0f}%", p.get("rationale",""), "wizard") for p in picks)
        picks_table = f"""
{_section_label("This Month's Positions")}
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:8px 14px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Symbol</th>
      <th style="padding:8px 14px;text-align:right;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Weight</th>
      <th style="padding:8px 14px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Thesis</th>
    </tr>
  </thead>
  <tbody>{picks_rows}</tbody>
</table>"""
    else:
        picks_table = '<p style="font-size:13px;color:#7d8590;margin:16px 0 0;">Wizard is holding current positions this month — no changes.</p>'

    body = eyebrow_html + greeting + wizard_block + picks_table + _cta_button(f"{site_url}/dashboard.html", "View Full Report")
    preheader = f"Wizard's monthly portfolio for {month} — {len(picks)} positions"
    return _wrap(platform, preheader, body)


# ═══════════════════════════════════════════════════════════════════
# CONSOLIDATED WRAPPER — multi-site header/footer
# ═══════════════════════════════════════════════════════════════════
def _wrap_consolidated(preheader: str, body_html: str) -> str:
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="dark"/>
<title>Wall St. Bots — Daily Report</title>
</head>
<body style="margin:0;padding:0;background:#06080d;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,system-ui,sans-serif;color:#e6edf3;-webkit-font-smoothing:antialiased;">

<!-- preheader -->
<span style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</span>

<table width="100%" cellpadding="0" cellspacing="0" style="background:#06080d;padding:28px 0 48px;">
  <tr><td align="center" style="padding:0 16px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

      <!-- ── HEADER ── -->
      <tr>
        <td style="background:#0d1117;border:1px solid #1e2633;border-bottom:2px solid #00d4ff;padding:18px 24px;border-radius:12px 12px 0 0;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <a href="https://wallstbots.tech" style="text-decoration:none;font-size:20px;font-weight:800;color:#e6edf3;letter-spacing:-0.5px;">
                  Wall St. <span style="color:#00d4ff;">Bots</span>
                </a>
                <div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#7d8590;margin-top:3px;">AI-Powered Trading Signals — Daily Report</div>
              </td>
              <td align="right">
                <a href="https://wallstbots.tech/dashboard.html" style="display:inline-block;background:#003d47;border:1px solid #00d4ff;color:#00d4ff;border-radius:6px;padding:7px 14px;font-size:11px;font-weight:700;text-decoration:none;white-space:nowrap;">Dashboard</a>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ── BODY ── -->
      <tr>
        <td style="background:#0d1117;border-left:1px solid #1e2633;border-right:1px solid #1e2633;padding:28px 24px;">
          {body_html}
        </td>
      </tr>

      <!-- ── FOOTER ── -->
      <tr>
        <td style="background:#0a0e16;border:1px solid #1e2633;border-top:none;padding:20px 24px;border-radius:0 0 12px 12px;text-align:center;">
          <p style="font-size:11px;color:#7d8590;margin:0 0 6px;">
            You're receiving this because you're subscribed to Wall St. Bots.
          </p>
          <p style="font-size:11px;margin:0 0 8px;">
            <a href="https://wallstbots.tech/dashboard.html" style="color:#00d4ff;text-decoration:none;">WallStBots</a>
            &nbsp;<span style="color:#1e2633;">·</span>&nbsp;
            <a href="https://bitbot13.tech/dashboard.html" style="color:#00d4ff;text-decoration:none;">BitBot13</a>
            &nbsp;<span style="color:#1e2633;">·</span>&nbsp;
            <a href="https://lvl13.tech/dashboard.html" style="color:#00d4ff;text-decoration:none;">Level XIII</a>
          </p>
          <p style="font-size:11px;margin:0;">
            <a href="https://wallstbots.tech/dashboard.html#email-prefs" style="color:#7d8590;text-decoration:none;">Email Preferences</a>
            &nbsp;<span style="color:#1e2633;">·</span>&nbsp;
            <span style="color:#4b5563;">&copy; {year} Wall St. Bots</span>
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>

</body>
</html>"""


def _platform_section_header(platform: str) -> str:
    """Divider bar between platform sections."""
    labels = {
        "wallstbots": ("Wall St. Bots", "https://wallstbots.tech", "#00d4ff"),
        "bitbot13":   ("BitBot13",       "https://bitbot13.tech",   "#ec4899"),
        "lvl13":      ("Level XIII",     "https://lvl13.tech",      "#a855f7"),
    }
    name, url, color = labels.get(platform, ("Wall St. Bots", "https://wallstbots.tech", "#00d4ff"))
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0 16px;">
  <tr>
    <td style="border-top:1px solid #1e2633;padding-top:20px;">
      <table cellpadding="0" cellspacing="0">
        <tr>
          <td style="padding-right:10px;border-right:2px solid {color};"></td>
          <td style="padding-left:10px;">
            <a href="{url}/dashboard.html" style="text-decoration:none;font-size:13px;font-weight:800;text-transform:uppercase;letter-spacing:1.2px;color:{color};">{name}</a>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


def _compact_signals_table(signals: list[dict], max_rows: int = 8) -> str:
    """Compact signal table for use inside a consolidated email section."""
    if not signals:
        return '<p style="font-size:12px;color:#7d8590;margin:10px 0 0;">No signals today.</p>'
    rows = "".join(
        _signal_row(
            s.get("symbol", ""),
            s.get("action", "HOLD"),
            s.get("reason", s.get("rationale", "")),
            s.get("price"),
        )
        for s in signals[:max_rows]
    )
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:7px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Symbol</th>
      <th style="padding:7px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Signal</th>
      <th style="padding:7px 12px;text-align:right;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Price</th>
      <th style="padding:7px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Reason</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""


def _portfolio_section(recipient: dict) -> str:
    """Render the user's portfolio signals across all platforms."""
    blocks = []
    platform_labels = [
        ("wallstbots", "Stocks", "#00d4ff"),
        ("bitbot13",   "Crypto", "#ec4899"),
        ("lvl13",      "AI / Quantum", "#a855f7"),
    ]
    for plat, label, color in platform_labels:
        signals = recipient.get(f"portfolio_signals_{plat}", [])
        if not signals:
            continue
        pill = f'<span style="display:inline-block;padding:2px 8px;border-radius:999px;background:rgba(0,0,0,0.3);border:1px solid {color};color:{color};font-size:9px;font-weight:800;letter-spacing:0.5px;text-transform:uppercase;margin-left:8px;">{label}</span>'
        blocks.append(
            f'<div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.7px;color:#7d8590;margin:16px 0 8px;">Your Portfolio{pill}</div>'
            + _compact_signals_table(signals, max_rows=10)
        )

    if not blocks:
        return '<p style="font-size:13px;color:#7d8590;margin:0 0 4px;">No active signals match your holdings today.</p>'
    return "".join(blocks)


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 5 — Consolidated Daily Report (all three sites)
# ═══════════════════════════════════════════════════════════════════
def build_consolidated_email(
    recipient: dict,
    platform_data: dict,
    is_weekly: bool = False,
    is_monthly: bool = False,
) -> str:
    """
    Build a single consolidated email covering all three platforms.
    Sections rendered depend on per-user preference flags:
      email_portfolio, email_wallstbots, email_bitbot13, email_lvl13
    """
    name      = recipient.get("first_name") or "Trader"
    today_str = date.today().strftime("%B %d, %Y")
    preheader = f"Your trading signals for {today_str} — Wall St. Bots, BitBot13 & Level XIII"

    show_portfolio  = recipient.get("email_portfolio",  True)
    show_wallstbots = recipient.get("email_wallstbots", True)
    show_bitbot13   = recipient.get("email_bitbot13",   True)
    show_lvl13      = recipient.get("email_lvl13",      True)

    sections = []

    # ── Greeting ──────────────────────────────────────────────────
    sections.append(f"""
<p style="font-size:15px;color:#adb8c6;margin:0 0 20px;line-height:1.6;">
  Hey <strong style="color:#e6edf3;">{name}</strong> — here's your daily trading report for <strong style="color:#e6edf3;">{today_str}</strong>.
</p>""")

    # ── 1. Portfolio signals ──────────────────────────────────────
    if show_portfolio:
        sections.append(_eyebrow("📊 Your Portfolio", "#facc15"))
        sections.append(_portfolio_section(recipient))

    # ── 2–4. Per-platform sections ────────────────────────────────
    platform_order = [
        ("wallstbots", show_wallstbots),
        ("bitbot13",   show_bitbot13),
        ("lvl13",      show_lvl13),
    ]

    for plat, enabled in platform_order:
        if not enabled:
            continue

        pdata    = platform_data.get(plat, {})
        funds    = pdata.get("funds", {})
        signals  = pdata.get("signals", [])
        site_url = SITE_URLS[plat]
        is_fresh = pdata.get("is_fresh", True)

        # ── Stale data guard ─────────────────────────────────────────────────
        # If this platform hasn't refreshed today (e.g. wallstbots/lvl13 on
        # weekends when only bitbot13 runs), show a brief "closed" note instead
        # of outdated Friday data.
        if not is_fresh:
            last_upd = pdata.get("last_updated", "recently")
            sections.append(_platform_section_header(plat))
            sections.append(f"""
<p style="font-size:13px;color:#7d8590;margin:8px 0 20px;padding:12px 16px;background:#141b27;border:1px solid #1e2633;border-radius:8px;line-height:1.5;">
  No update today — markets are closed for this platform.
  &nbsp;<a href="{site_url}/dashboard.html" style="color:#00d4ff;text-decoration:none;font-weight:600;">View last update →</a>
</p>""")
            continue

        # Extract BOT13 strategy (key may be 'bot13' or 'BOT13')
        bot13_data = funds.get("bot13") or funds.get("BOT13") or {}
        strategy   = bot13_data.get("strategy") or bot13_data
        decision   = strategy.get("decision", "HOLD")
        rationale  = strategy.get("rationale", "No analysis available.")
        picks      = strategy.get("picks", [])

        sections.append(_platform_section_header(plat))

        # BOT13 strategy card
        sections.append(_strategy_card("bot13", f"BOT13 · {today_str}", decision, rationale))

        # Picks table (if TRADE decision)
        if picks and decision == "TRADE":
            picks_rows = "".join(
                _pick_row(p["symbol"], f"{p['weight']*100:.0f}%", p.get("rationale",""), "bot13")
                for p in picks
            )
            sections.append(f"""
{_section_label("Positions Entered")}
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;margin-bottom:16px;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:7px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Symbol</th>
      <th style="padding:7px 12px;text-align:right;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Allocation</th>
      <th style="padding:7px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Rationale</th>
    </tr>
  </thead>
  <tbody>{picks_rows}</tbody>
</table>""")

        # Top signals
        if signals:
            sections.append(_section_label(f"Top Signals — {SITE_NAMES[plat]}"))
            sections.append(_compact_signals_table(signals, max_rows=8))

        # Oracle / weekly picks (if is_weekly)
        if is_weekly:
            oracle_data = funds.get("oracle") or funds.get("ORACLE") or {}
            oracle_strat = oracle_data.get("strategy") or oracle_data
            oracle_picks = oracle_strat.get("picks", [])
            if oracle_picks:
                oracle_rows = "".join(
                    _pick_row(p["symbol"], f"{p['weight']*100:.0f}%", p.get("rationale",""), "oracle")
                    for p in oracle_picks
                )
                sections.append(f"""
{_section_label("Oracle — Weekly Picks")}
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;margin-bottom:16px;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:7px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Symbol</th>
      <th style="padding:7px 12px;text-align:right;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Weight</th>
      <th style="padding:7px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Thesis</th>
    </tr>
  </thead>
  <tbody>{oracle_rows}</tbody>
</table>""")

        # Wizard / monthly picks (if is_monthly)
        if is_monthly:
            wizard_data = funds.get("wizard") or funds.get("WIZARD") or {}
            wizard_strat = wizard_data.get("strategy") or wizard_data
            wizard_picks = wizard_strat.get("picks", [])
            if wizard_picks:
                wizard_rows = "".join(
                    _pick_row(p["symbol"], f"{p['weight']*100:.0f}%", p.get("rationale",""), "wizard")
                    for p in wizard_picks
                )
                sections.append(f"""
{_section_label("Wizard — Monthly Portfolio")}
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2633;border-radius:10px;overflow:hidden;border-collapse:collapse;margin-bottom:16px;">
  <thead>
    <tr style="background:#141b27;">
      <th style="padding:7px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Symbol</th>
      <th style="padding:7px 12px;text-align:right;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Weight</th>
      <th style="padding:7px 12px;text-align:left;font-size:9px;color:#7d8590;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;">Thesis</th>
    </tr>
  </thead>
  <tbody>{wizard_rows}</tbody>
</table>""")

        # Dashboard CTA (compact)
        sections.append(f"""
<div style="text-align:right;margin-top:12px;">
  <a href="{site_url}/dashboard.html" style="font-size:11px;color:#00d4ff;text-decoration:none;font-weight:600;">View {SITE_NAMES[plat]} Dashboard →</a>
</div>""")

    # ── Nothing enabled guard ─────────────────────────────────────
    if not (show_portfolio or show_wallstbots or show_bitbot13 or show_lvl13):
        sections.append(
            '<p style="font-size:13px;color:#7d8590;margin:20px 0;">You have no email sections enabled. '
            '<a href="https://wallstbots.tech/dashboard.html#email-prefs" style="color:#00d4ff;">Update preferences →</a></p>'
        )

    body = "\n".join(sections)
    return _wrap_consolidated(preheader, body)
