"""
email_service.py
----------------
Resend-based email service for WallStBots / BitBot13 / Level XIII.
Print edition aesthetic — white background, all-black monospace typography,
no color. BUY = heavy outlined box, SELL = filled black inverted, HOLD = dashed.
Mobile-first, universally compatible with all email clients.

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
PLATFORM_LABELS = {
    "wallstbots": "WALL ST. BOTS",
    "bitbot13":   "CRYPTO",
    "lvl13":      "AI & QUANTUM",
}

# Kept for pick tables (allocation color only)
BOT_COLORS = {
    "bot13":     {"bg": "#0d0d0d", "abbr": "B13"},
    "oracle":    {"bg": "#555555", "abbr": "OR"},
    "wizard":    {"bg": "#333333", "abbr": "WZ"},
    "equalizer": {"bg": "#0d0d0d", "abbr": "EQ"},
    "titan":     {"bg": "#333333", "abbr": "TI"},
}


# ── Resend sender ──────────────────────────────────────────────────────────────
def send_email(to: str, subject: str, html: str) -> bool:
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


# ── Visual helpers ─────────────────────────────────────────────────────────────

def _mkt_status() -> str:
    return "MKT CLOSED" if datetime.utcnow().weekday() >= 5 else "MKT OPEN"


def _signal_pill(action: str) -> str:
    """Monochrome signal badge: BUY=outlined, SELL=filled black, HOLD=dashed."""
    a = action.upper()
    if a in ("BUY", "STRONG BUY"):
        return (
            '<span style="border:2px solid #0d0d0d;font-size:8px;font-weight:900;'
            'padding:2px 7px;letter-spacing:2px;color:#0d0d0d;font-family:\'Courier New\',Courier,monospace;'
            f'white-space:nowrap;">{a}</span>'
        )
    elif a in ("SELL", "STRONG SELL"):
        return (
            '<span style="background:#0d0d0d;color:#ffffff;font-size:8px;font-weight:900;'
            'padding:3px 7px;letter-spacing:2px;font-family:\'Courier New\',Courier,monospace;'
            'white-space:nowrap;">SELL</span>'
        )
    else:
        return (
            '<span style="border:1px dashed #aaaaaa;font-size:8px;font-weight:400;'
            'padding:2px 5px;letter-spacing:2px;color:#888888;font-family:\'Courier New\',Courier,monospace;'
            'white-space:nowrap;">HOLD</span>'
        )


def _signal_summary_bar(signals: list[dict]) -> str:
    buy  = sum(1 for s in signals if s.get("action","").upper() in ("BUY","STRONG BUY"))
    hold = sum(1 for s in signals if s.get("action","").upper() == "HOLD")
    sell = sum(1 for s in signals if s.get("action","").upper() in ("SELL","STRONG SELL"))
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border-bottom:1px solid #dddddd;border-collapse:collapse;margin-bottom:0;">
  <tr>
    <td width="33%" align="center" style="padding:12px 0;border-right:1px solid #cccccc;">
      <div style="font-family:'Courier New',Courier,monospace;font-size:28px;font-weight:900;color:#0d0d0d;line-height:1;letter-spacing:-1px;">{buy}</div>
      <div style="font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:700;letter-spacing:4px;margin-top:3px;color:#0d0d0d;">BUY</div>
    </td>
    <td width="33%" align="center" style="padding:12px 0;border-right:1px solid #cccccc;">
      <div style="font-family:'Courier New',Courier,monospace;font-size:28px;font-weight:400;color:#888888;line-height:1;letter-spacing:-1px;">{hold}</div>
      <div style="font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:400;letter-spacing:4px;margin-top:3px;color:#888888;">HOLD</div>
    </td>
    <td width="33%" align="center" style="padding:12px 0;">
      <div style="font-family:'Courier New',Courier,monospace;font-size:28px;font-weight:900;color:#0d0d0d;line-height:1;letter-spacing:-1px;">{sell}</div>
      <div style="font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:700;letter-spacing:4px;margin-top:3px;color:#0d0d0d;">SELL</div>
    </td>
  </tr>
</table>"""


def _decision_card(decision: str, platform_label: str,
                   confidence=None, target=None, rationale: str = "") -> str:
    d = decision.upper()
    is_sell = d in ("SELL", "STRONG SELL")
    is_hold = d not in ("BUY", "STRONG BUY", "TRADE", "SELL", "STRONG SELL")
    display = "BUY" if d == "TRADE" else ("SELL" if is_sell else ("HOLD" if is_hold else d))

    if is_sell:
        badge = (
            f'<div style="background:#0d0d0d;padding:10px 14px;text-align:center;display:inline-block;">'
            f'<span style="font-family:\'Courier New\',Courier,monospace;font-size:28px;'
            f'font-weight:900;color:#ffffff;letter-spacing:3px;">{display}</span></div>'
        )
    elif is_hold:
        badge = (
            f'<div style="border:2px dashed #888888;padding:10px 14px;text-align:center;display:inline-block;">'
            f'<span style="font-family:\'Courier New\',Courier,monospace;font-size:28px;'
            f'font-weight:400;color:#888888;letter-spacing:3px;">{display}</span></div>'
        )
    else:
        badge = (
            f'<div style="border:3px solid #0d0d0d;padding:10px 14px;text-align:center;display:inline-block;">'
            f'<span style="font-family:\'Courier New\',Courier,monospace;font-size:28px;'
            f'font-weight:900;color:#0d0d0d;letter-spacing:3px;">{display}</span></div>'
        )

    conf_str   = f"{confidence}%" if confidence is not None else "&mdash;"
    target_str = str(target)      if target     is not None else "&mdash;"

    rationale_row = ""
    if rationale:
        rationale_row = f"""
  <tr>
    <td colspan="3" style="padding:10px 16px 14px;border-top:1px dotted #cccccc;">
      <p style="font-size:11px;color:#444444;line-height:1.65;margin:0;
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-style:italic;">{rationale[:280]}</p>
    </td>
  </tr>"""

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border-bottom:1px solid #dddddd;border-collapse:collapse;">
  <tr>
    <td colspan="3" style="padding:10px 16px 8px;">
      <span style="font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:700;
        color:#888888;letter-spacing:3px;">BOT13 DECISION &middot; {platform_label}</span>
    </td>
  </tr>
  <tr>
    <td style="padding:10px 14px 14px;vertical-align:middle;">{badge}</td>
    <td style="padding:10px 12px 14px;vertical-align:middle;text-align:center;
      border-left:1px solid #e0e0e0;">
      <div style="font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:700;
        letter-spacing:2px;color:#888888;margin-bottom:3px;">CONFIDENCE</div>
      <div style="font-family:'Courier New',Courier,monospace;font-size:22px;
        font-weight:900;color:#0d0d0d;line-height:1;">{conf_str}</div>
    </td>
    <td style="padding:10px 14px 14px;vertical-align:middle;text-align:center;
      border-left:1px solid #e0e0e0;">
      <div style="font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:700;
        letter-spacing:2px;color:#888888;margin-bottom:3px;">30D TARGET</div>
      <div style="font-family:'Courier New',Courier,monospace;font-size:22px;
        font-weight:900;color:#0d0d0d;line-height:1;">{target_str}</div>
    </td>
  </tr>{rationale_row}
</table>"""


def _terminal_signal_row(symbol: str, action: str,
                          chg_pct=None, score=None, company: str = "") -> str:
    a = action.upper()
    is_sell = a in ("SELL", "STRONG SELL")
    is_hold = a == "HOLD"
    ticker_weight = "400" if is_hold else "900"
    ticker_color  = "#888888" if is_hold else "#0d0d0d"

    if chg_pct is not None:
        try:
            v = float(chg_pct)
            chg_str = f"+{v:.1f}%" if v > 0 else f"{v:.1f}%"
        except (TypeError, ValueError):
            chg_str = str(chg_pct)
    else:
        chg_str = "&mdash;"

    score_str = str(int(score)) if score is not None else "&mdash;"
    co_line   = (f'<div style="font-size:9px;color:#aaaaaa;margin-top:1px;'
                 f'font-family:-apple-system,sans-serif;">{company[:18]}</div>'
                 if company else "")

    return f"""
<tr style="border-bottom:1px solid #eeeeee;">
  <td style="padding:8px 8px 8px 0;">
    <div style="font-family:'Courier New',Courier,monospace;font-size:14px;
      font-weight:{ticker_weight};color:{ticker_color};">{symbol}</div>
    {co_line}
  </td>
  <td style="padding:8px;white-space:nowrap;">{_signal_pill(action)}</td>
  <td style="padding:8px;text-align:right;font-family:'Courier New',Courier,monospace;
    font-size:11px;font-weight:700;color:{'#888888' if is_hold else '#0d0d0d'};
    white-space:nowrap;">{chg_str}</td>
  <td style="padding:8px 0 8px 8px;text-align:right;font-family:'Courier New',Courier,monospace;
    font-size:11px;font-weight:700;color:{'#888888' if is_hold else '#0d0d0d'};
    white-space:nowrap;">{score_str}</td>
</tr>"""


def _terminal_signals_table(signals: list[dict], max_rows: int = 8) -> str:
    if not signals:
        return ('<p style="font-family:\'Courier New\',Courier,monospace;font-size:10px;'
                'color:#888888;margin:8px 0;letter-spacing:2px;">NO SIGNALS TODAY</p>')
    rows = ""
    for s in signals[:max_rows]:
        chg     = s.get("change_pct") or s.get("pct_change") or s.get("change")
        score   = s.get("score") or s.get("signal_score")
        company = s.get("company") or s.get("name") or ""
        rows   += _terminal_signal_row(s.get("symbol",""), s.get("action","HOLD"), chg, score, company)
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:4px;">
  <tr>
    <th style="padding:4px 8px 8px 0;text-align:left;font-family:'Courier New',Courier,monospace;
      font-size:8px;font-weight:700;color:#888888;letter-spacing:2px;border-bottom:2px solid #0d0d0d;">TICKER</th>
    <th style="padding:4px 8px 8px;text-align:left;font-family:'Courier New',Courier,monospace;
      font-size:8px;font-weight:700;color:#888888;letter-spacing:2px;border-bottom:2px solid #0d0d0d;">ACTION</th>
    <th style="padding:4px 8px 8px;text-align:right;font-family:'Courier New',Courier,monospace;
      font-size:8px;font-weight:700;color:#888888;letter-spacing:2px;border-bottom:2px solid #0d0d0d;">CHG%</th>
    <th style="padding:4px 0 8px 8px;text-align:right;font-family:'Courier New',Courier,monospace;
      font-size:8px;font-weight:700;color:#888888;letter-spacing:2px;border-bottom:2px solid #0d0d0d;">SCR</th>
  </tr>
  {rows}
</table>"""


def _portfolio_tiles(signals: list[dict], _accent: str = "") -> str:
    """3-per-row portfolio tiles in monochrome print style."""
    if not signals:
        return ""
    tiles     = signals[:9]
    row_cells, rows_html = [], ""
    for s in tiles:
        a      = s.get("action","HOLD").upper()
        is_sell = a in ("SELL","STRONG SELL")
        is_hold = a == "HOLD"
        sym    = s.get("symbol","?")
        score  = s.get("score") or s.get("signal_score")
        sc_str = f" &middot; {int(score)}" if score is not None else ""

        if is_sell:
            box_style = "background:#0d0d0d;padding:9px 4px;text-align:center;"
            sym_style = "font-family:'Courier New',Courier,monospace;font-size:13px;font-weight:900;color:#ffffff;"
            lbl_style = "font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:700;margin-top:3px;letter-spacing:2px;color:#aaaaaa;"
        elif is_hold:
            box_style = "border:1px dashed #aaaaaa;padding:9px 4px;text-align:center;"
            sym_style = "font-family:'Courier New',Courier,monospace;font-size:13px;font-weight:400;color:#888888;"
            lbl_style = "font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:400;margin-top:3px;letter-spacing:2px;color:#888888;"
        else:
            box_style = "border:2px solid #0d0d0d;padding:9px 4px;text-align:center;"
            sym_style = "font-family:'Courier New',Courier,monospace;font-size:13px;font-weight:900;color:#0d0d0d;"
            lbl_style = "font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:700;margin-top:3px;letter-spacing:2px;color:#0d0d0d;"

        row_cells.append(
            f'<td width="33%" style="padding:3px;vertical-align:top;">'
            f'<div style="{box_style}">'
            f'<div style="{sym_style}">{sym}</div>'
            f'<div style="{lbl_style}">{a}{sc_str}</div>'
            f'</div></td>'
        )
        if len(row_cells) == 3:
            rows_html += f"<tr>{''.join(row_cells)}</tr>"
            row_cells = []
    if row_cells:
        while len(row_cells) < 3:
            row_cells.append('<td width="33%" style="padding:3px;"></td>')
        rows_html += f"<tr>{''.join(row_cells)}</tr>"
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:4px;">
  {rows_html}
</table>"""


def _picks_table(picks: list[dict], bot_key: str = "bot13") -> str:
    if not picks:
        return ""
    rows = ""
    for p in picks:
        alloc  = f"{p['weight']*100:.0f}%" if p.get("weight") is not None else "&mdash;"
        thesis = (p.get("rationale") or "")[:110]
        rows  += (
            f'<tr style="border-bottom:1px solid #eeeeee;">'
            f'<td style="padding:8px 10px 8px 0;font-family:\'Courier New\',Courier,monospace;'
            f'font-size:13px;font-weight:900;color:#0d0d0d;white-space:nowrap;">{p.get("symbol","")}</td>'
            f'<td style="padding:8px 10px;font-family:\'Courier New\',Courier,monospace;'
            f'font-size:12px;font-weight:700;color:#0d0d0d;text-align:right;white-space:nowrap;">{alloc}</td>'
            f'<td style="padding:8px 0 8px 10px;font-size:11px;color:#555555;'
            f'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;">{thesis}</td>'
            f'</tr>'
        )
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:4px;">
  <tr style="border-bottom:2px solid #0d0d0d;">
    <th style="padding:4px 10px 8px 0;text-align:left;font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:700;color:#888888;letter-spacing:2px;">SYMBOL</th>
    <th style="padding:4px 10px 8px;text-align:right;font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:700;color:#888888;letter-spacing:2px;">ALLOC</th>
    <th style="padding:4px 0 8px 10px;text-align:left;font-family:'Courier New',Courier,monospace;font-size:8px;font-weight:700;color:#888888;letter-spacing:2px;">THESIS</th>
  </tr>
  {rows}
</table>"""


def _section_label(text: str) -> str:
    return (
        f'<div style="font-family:\'Courier New\',Courier,monospace;font-size:8px;font-weight:700;'
        f'letter-spacing:3px;color:#888888;margin:14px 0 8px;">{text}</div>'
    )


def _section_divider(platform: str, label_override: str = "") -> str:
    label = label_override or SITE_NAMES.get(platform, platform).upper()
    url   = SITE_URLS.get(platform, "#")
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:16px 0 12px;">
  <tr><td style="border-top:2px solid #0d0d0d;padding-top:12px;">
    <a href="{url}" style="text-decoration:none;">
      <span style="font-family:'Courier New',Courier,monospace;font-size:9px;font-weight:700;
        color:#0d0d0d;letter-spacing:3px;border-left:3px solid #0d0d0d;padding-left:8px;">{label}</span>
    </a>
  </td></tr>
</table>"""


def _dashboard_link(platform: str) -> str:
    url  = SITE_URLS.get(platform, "#")
    name = SITE_NAMES.get(platform, platform).upper()
    return (
        f'<div style="text-align:right;margin:8px 0 4px;">'
        f'<a href="{url}/dashboard.html" style="font-family:\'Courier New\',Courier,monospace;'
        f'font-size:9px;font-weight:700;color:#0d0d0d;text-decoration:underline;letter-spacing:1px;">'
        f'VIEW {name} DASHBOARD &rarr;</a></div>'
    )


def _cta_button(url: str, text: str) -> str:
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:24px;">
  <tr><td align="center">
    <a href="{url}" style="display:inline-block;border:2px solid #0d0d0d;color:#0d0d0d;
      padding:12px 28px;font-family:'Courier New',Courier,monospace;font-size:11px;
      font-weight:700;text-decoration:none;letter-spacing:2px;">{text} &rarr;</a>
  </td></tr>
</table>"""


def _portfolio_section(recipient: dict) -> str:
    blocks = []
    config = [
        ("wallstbots", "STOCKS"),
        ("bitbot13",   "CRYPTO"),
        ("lvl13",      "AI / QUANTUM"),
    ]
    for plat, label in config:
        if not recipient.get(f"email_{plat}", True):
            continue
        signals = recipient.get(f"portfolio_signals_{plat}", [])
        if not signals:
            continue
        blocks.append(_section_label(f"{label} SIGNALS"))
        blocks.append(_portfolio_tiles(signals))
    if not blocks:
        return ('<p style="font-family:\'Courier New\',Courier,monospace;font-size:10px;'
                'color:#888888;margin:0 0 12px;letter-spacing:2px;">NO PORTFOLIO MATCHES TODAY</p>')
    return "".join(blocks)


# ── Email shell wrappers ───────────────────────────────────────────────────────

def _build_header_row(logo_text: str, date_str: str, time_str: str) -> str:
    mkt = _mkt_status()
    return f"""
      <!-- black header bar -->
      <tr>
        <td bgcolor="#0d0d0d" style="background-color:#0d0d0d;padding:14px 18px;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td style="vertical-align:middle;">
              <div style="font-family:'Courier New',Courier,monospace;font-size:16px;
                font-weight:700;color:#ffffff;letter-spacing:5px;">{logo_text}</div>
              <div style="font-family:'Courier New',Courier,monospace;font-size:9px;
                color:#777777;margin-top:4px;letter-spacing:2px;">{date_str} &nbsp;|&nbsp; {time_str} &nbsp;|&nbsp; {mkt}</div>
            </td>
          </tr></table>
        </td>
      </tr>
      <!-- newspaper double rule -->
      <tr><td bgcolor="#0d0d0d" height="3" style="background-color:#0d0d0d;font-size:0;line-height:0;">&nbsp;</td></tr>
      <tr><td bgcolor="#ffffff" height="2" style="background-color:#ffffff;font-size:0;line-height:0;">&nbsp;</td></tr>
      <tr><td bgcolor="#0d0d0d" height="1" style="background-color:#0d0d0d;font-size:0;line-height:0;">&nbsp;</td></tr>"""


def _build_footer_row(site_name: str, site_url: str, year: int, extra: str = "") -> str:
    return f"""
      <!-- footer rule -->
      <tr><td bgcolor="#0d0d0d" height="3" style="background-color:#0d0d0d;font-size:0;line-height:0;">&nbsp;</td></tr>
      <tr>
        <td bgcolor="#f5f5f3" style="background-color:#f5f5f3;padding:12px 18px;">
          {extra}
          <div style="font-family:'Courier New',Courier,monospace;font-size:9px;
            color:#aaaaaa;line-height:1.7;">
            You're receiving this because you're subscribed to {site_name}.<br>
            <a href="{site_url}/dashboard.html#email-prefs"
              style="color:#555555;text-decoration:none;">Unsubscribe</a>
            &nbsp;&middot;&nbsp;
            <a href="{site_url}/dashboard.html#email-prefs"
              style="color:#555555;text-decoration:none;">Preferences</a>
            &nbsp;&middot;&nbsp;
            <span>&copy; {year} {site_name}</span>
          </div>
        </td>
      </tr>"""


def _wrap(platform: str, preheader: str, body_html: str) -> str:
    site_name = SITE_NAMES.get(platform, "WallStBots")
    site_url  = SITE_URLS.get(platform, "https://wallstbots.tech")
    year      = datetime.now().year
    now       = datetime.now()
    date_str  = now.strftime("%b %d, %Y").upper()
    time_str  = now.strftime("%H:%M ET")
    logos     = {"wallstbots": "WALL ST. BOTS", "bitbot13": "BITBOT13", "lvl13": "LEVEL XIII"}
    logo      = logos.get(platform, site_name.upper())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{site_name}</title>
</head>
<body bgcolor="#f0f0ee" style="margin:0;padding:0;background-color:#f0f0ee;
  font-family:'Courier New',Courier,monospace;-webkit-font-smoothing:antialiased;">

<span style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</span>

<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#f0f0ee"
  style="background-color:#f0f0ee;padding:24px 0 48px;">
  <tr><td align="center" style="padding:0 12px;">
    <table width="100%" cellpadding="0" cellspacing="0"
      style="max-width:600px;background:#ffffff;border:1px solid #aaaaaa;">
      {_build_header_row(logo, date_str, time_str)}
      <tr>
        <td bgcolor="#ffffff" style="background-color:#ffffff;padding:0;">
          {body_html}
        </td>
      </tr>
      {_build_footer_row(site_name, site_url, year)}
    </table>
  </td></tr>
</table>

</body>
</html>"""


def _wrap_consolidated(preheader: str, body_html: str) -> str:
    year     = datetime.now().year
    now      = datetime.now()
    date_str = now.strftime("%b %d, %Y").upper()
    time_str = now.strftime("%H:%M ET")
    extra    = """
          <div style="font-family:'Courier New',Courier,monospace;font-size:9px;color:#aaaaaa;margin-bottom:6px;">
            <a href="https://wallstbots.tech" style="color:#555555;text-decoration:none;">WallStBots</a>
            &nbsp;&middot;&nbsp;
            <a href="https://bitbot13.tech" style="color:#555555;text-decoration:none;">BitBot13</a>
            &nbsp;&middot;&nbsp;
            <a href="https://lvl13.tech" style="color:#555555;text-decoration:none;">Level XIII</a>
          </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Wall St. Bots &mdash; Daily Report</title>
</head>
<body bgcolor="#f0f0ee" style="margin:0;padding:0;background-color:#f0f0ee;
  font-family:'Courier New',Courier,monospace;-webkit-font-smoothing:antialiased;">

<span style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</span>

<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#f0f0ee"
  style="background-color:#f0f0ee;padding:24px 0 48px;">
  <tr><td align="center" style="padding:0 12px;">
    <table width="100%" cellpadding="0" cellspacing="0"
      style="max-width:600px;background:#ffffff;border:1px solid #aaaaaa;">
      {_build_header_row("WALL ST. BOTS", date_str, time_str)}
      <tr>
        <td bgcolor="#ffffff" style="background-color:#ffffff;padding:0;">
          {body_html}
        </td>
      </tr>
      {_build_footer_row("Wall St. Bots", "https://wallstbots.tech", year, extra)}
    </table>
  </td></tr>
</table>

</body>
</html>"""


# ── Section padding wrapper ────────────────────────────────────────────────────
def _pad(html: str, alt_bg: bool = False) -> str:
    bg = '#f9f9f7' if alt_bg else '#ffffff'
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f'<tr><td bgcolor="{bg}" style="background-color:{bg};padding:14px 18px;">{html}</td></tr>'
        f'</table>'
    )


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 1 — Daily Signals (single-platform)
# ═══════════════════════════════════════════════════════════════════
def build_daily_signals_email(
    platform: str,
    site_signals: list[dict],
    bot13_strategy: dict,
    leaderboard: list[dict],
    recipient: dict,
) -> str:
    today_str  = date.today().strftime("%B %d, %Y")
    decision   = bot13_strategy.get("decision", "HOLD")
    rationale  = bot13_strategy.get("rationale", "")
    picks      = bot13_strategy.get("picks", [])
    confidence = bot13_strategy.get("confidence")
    target     = bot13_strategy.get("target") or bot13_strategy.get("price_target")

    body = ""

    if site_signals:
        body += _signal_summary_bar(site_signals)

    body += _pad(_decision_card(
        decision, PLATFORM_LABELS.get(platform, platform.upper()),
        confidence, target, rationale,
    ).strip())

    actionable = [s for s in site_signals
                  if s.get("action","").upper() in ("STRONG BUY","BUY","SELL","STRONG SELL")][:8]

    if picks and decision in ("TRADE", "BUY", "STRONG BUY"):
        body += _pad(_section_label("POSITIONS") + _picks_table(picks[:6]), alt_bg=True)

    if actionable:
        body += _pad(_section_label("TOP SIGNALS") + _terminal_signals_table(actionable))

    port_signals = recipient.get("portfolio_signals", [])
    if port_signals:
        body += _pad(_section_label("YOUR PORTFOLIO") + _portfolio_tiles(port_signals), alt_bg=True)

    body += _pad(_cta_button(f"{SITE_URLS[platform]}/dashboard.html", "OPEN DASHBOARD"))

    preheader = f"BOT13: {decision} · {len(actionable)} signals · {today_str}"
    return _wrap(platform, preheader, body)


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 2 — Bot13 Trade Alert
# ═══════════════════════════════════════════════════════════════════
def build_bot13_alert_email(platform: str, strategy: dict, recipient: dict) -> str:
    today_str  = date.today().strftime("%B %d, %Y")
    decision   = strategy.get("decision", "HOLD")
    rationale  = strategy.get("rationale", "")
    picks      = strategy.get("picks", [])
    confidence = strategy.get("confidence")
    target     = strategy.get("target") or strategy.get("price_target")

    body = _pad(_decision_card(
        decision, PLATFORM_LABELS.get(platform, platform.upper()),
        confidence, target, rationale,
    ).strip())

    if picks:
        body += _pad(_section_label("POSITIONS ENTERED") + _picks_table(picks), alt_bg=True)

    body += _pad(_cta_button(f"{SITE_URLS[platform]}/dashboard.html", "VIEW DASHBOARD"))

    preheader = f"BOT13 {decision} — {today_str}"
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
    today_str  = date.today().strftime("%B %d, %Y")
    week       = oracle_strategy.get("week", str(date.today()))
    decision   = oracle_strategy.get("decision", "HOLD")
    rationale  = oracle_strategy.get("rationale", "")
    picks      = oracle_strategy.get("picks", [])
    confidence = oracle_strategy.get("confidence")

    body  = _pad(_section_label(f"ORACLE &mdash; WEEK OF {week.upper()}")
                 + _decision_card(decision, PLATFORM_LABELS.get(platform, platform.upper()),
                                  confidence, None, rationale).strip())

    if picks:
        body += _pad(_section_label("THIS WEEK'S POSITIONS") + _picks_table(picks, "oracle"), alt_bg=True)
    else:
        body += _pad('<p style="font-size:11px;color:#888888;margin:8px 0;font-family:-apple-system,sans-serif;">Oracle is holding cash this week.</p>')

    body += _pad(_cta_button(f"{SITE_URLS[platform]}/dashboard.html", "TRACK PERFORMANCE"))
    preheader = f"Oracle weekly picks — {len(picks)} positions · {today_str}"
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
    month      = date.today().strftime("%B %Y")
    today_str  = date.today().strftime("%B %d, %Y")
    decision   = wizard_strategy.get("decision", "HOLD")
    rationale  = wizard_strategy.get("rationale", "")
    picks      = wizard_strategy.get("picks", [])
    confidence = wizard_strategy.get("confidence")

    body  = _pad(_section_label(f"WIZARD &mdash; {month.upper()}")
                 + _decision_card(decision, PLATFORM_LABELS.get(platform, platform.upper()),
                                  confidence, None, rationale).strip())

    if picks:
        body += _pad(_section_label("THIS MONTH'S POSITIONS") + _picks_table(picks, "wizard"), alt_bg=True)
    else:
        body += _pad('<p style="font-size:11px;color:#888888;margin:8px 0;font-family:-apple-system,sans-serif;">Wizard is holding current positions.</p>')

    body += _pad(_cta_button(f"{SITE_URLS[platform]}/dashboard.html", "VIEW FULL REPORT"))
    preheader = f"Wizard monthly portfolio — {month} · {len(picks)} positions"
    return _wrap(platform, preheader, body)


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 5 — Consolidated Daily Report (all three sites)
# ═══════════════════════════════════════════════════════════════════
def build_consolidated_email(
    recipient: dict,
    platform_data: dict,
    is_weekly: bool = False,
    is_monthly: bool = False,
) -> str:
    today_str = date.today().strftime("%B %d, %Y")
    preheader = f"BOT13 Daily Report &mdash; {today_str}"

    show_portfolio  = recipient.get("email_portfolio",  True)
    show_wallstbots = recipient.get("email_wallstbots", True)
    show_bitbot13   = recipient.get("email_bitbot13",   True)
    show_lvl13      = recipient.get("email_lvl13",      True)

    body = ""

    # Combined signal count bar
    all_signals: list[dict] = []
    for plat, enabled in [("wallstbots", show_wallstbots),
                           ("bitbot13",   show_bitbot13),
                           ("lvl13",      show_lvl13)]:
        if enabled:
            pd = platform_data.get(plat, {})
            if pd.get("is_fresh", True):
                all_signals.extend(pd.get("signals", []))
    if all_signals:
        body += _signal_summary_bar(all_signals)

    alt = False
    for plat, enabled in [("wallstbots", show_wallstbots),
                           ("bitbot13",   show_bitbot13),
                           ("lvl13",      show_lvl13)]:
        if not enabled:
            continue

        pdata    = platform_data.get(plat, {})
        funds    = pdata.get("funds", {})
        signals  = pdata.get("signals", [])
        site_url = SITE_URLS[plat]
        is_fresh = pdata.get("is_fresh", True)

        body += _pad(_section_divider(plat).strip(), alt_bg=alt)
        alt = not alt

        if not is_fresh:
            body += _pad(
                f'<p style="font-family:\'Courier New\',Courier,monospace;font-size:10px;'
                f'color:#888888;margin:4px 0 8px;letter-spacing:1px;">MKT CLOSED &mdash; '
                f'<a href="{site_url}/dashboard.html" style="color:#0d0d0d;">VIEW LAST UPDATE &rarr;</a></p>',
                alt_bg=alt
            )
            continue

        bot13_data = funds.get("bot13") or funds.get("BOT13") or {}
        strategy   = bot13_data.get("strategy") or bot13_data
        decision   = strategy.get("decision", "HOLD")
        rationale  = strategy.get("rationale", "")
        picks      = strategy.get("picks", [])
        confidence = strategy.get("confidence")
        target     = strategy.get("target") or strategy.get("price_target")

        body += _pad(
            _decision_card(decision, PLATFORM_LABELS[plat], confidence, target, rationale).strip(),
            alt_bg=alt
        )
        alt = not alt

        if picks and decision in ("TRADE", "BUY", "STRONG BUY"):
            body += _pad(_section_label("POSITIONS") + _picks_table(picks), alt_bg=alt)
            alt = not alt

        if signals:
            actionable = [s for s in signals
                          if s.get("action","").upper() in ("STRONG BUY","BUY","SELL","STRONG SELL")][:6]
            display = actionable if actionable else signals[:6]
            body += _pad(_section_label("TOP SIGNALS") + _terminal_signals_table(display), alt_bg=alt)
            alt = not alt

        if is_weekly:
            od = funds.get("oracle") or funds.get("ORACLE") or {}
            os = od.get("strategy") or od
            op = os.get("picks", [])
            if op:
                body += _pad(_section_label("ORACLE &mdash; WEEKLY PICKS") + _picks_table(op, "oracle"), alt_bg=alt)
                alt = not alt

        if is_monthly:
            wd = funds.get("wizard") or funds.get("WIZARD") or {}
            ws = wd.get("strategy") or wd
            wp = ws.get("picks", [])
            if wp:
                body += _pad(_section_label("WIZARD &mdash; MONTHLY PORTFOLIO") + _picks_table(wp, "wizard"), alt_bg=alt)
                alt = not alt

        body += _pad(_dashboard_link(plat), alt_bg=alt)
        alt = not alt

    # Portfolio section
    if show_portfolio:
        has_any = any(
            recipient.get(f"portfolio_signals_{p}", [])
            for p in ("wallstbots","bitbot13","lvl13")
            if recipient.get(f"email_{p}", True)
        )
        if has_any:
            body += _pad(
                '<div style="font-family:\'Courier New\',Courier,monospace;font-size:9px;'
                'font-weight:700;color:#0d0d0d;letter-spacing:3px;border-left:3px solid #0d0d0d;'
                'padding-left:8px;margin-bottom:12px;">YOUR PORTFOLIO</div>'
                + _portfolio_section(recipient),
                alt_bg=alt
            )

    if not any([show_portfolio, show_wallstbots, show_bitbot13, show_lvl13]):
        body += _pad(
            '<p style="font-family:\'Courier New\',Courier,monospace;font-size:10px;'
            'color:#888888;margin:16px 0;letter-spacing:2px;">NO SECTIONS ENABLED &mdash; '
            '<a href="https://wallstbots.tech/dashboard.html#email-prefs" '
            'style="color:#0d0d0d;">UPDATE PREFERENCES &rarr;</a></p>'
        )

    return _wrap_consolidated(preheader, body)
