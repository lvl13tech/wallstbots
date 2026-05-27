"""
email_service.py
----------------
Resend-based email service for WallStBots / BitBot13 / Level XIII.
Bloomberg terminal aesthetic — monospace tickers, dark panels,
BUY/HOLD/SELL count bar, compact decision cards. Mobile-first.

Design:
  bg=#06080d  panel=#0d1117  border=#1e2533
  text=#e6edf3  muted=#3a4a5e  teal=#00d4ff
  buy=#00e676   hold=#ffaa00  sell=#ff4457

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
PLATFORM_COLORS = {
    "wallstbots": "#00d4ff",
    "bitbot13":   "#ff4457",
    "lvl13":      "#a855f7",
}
PLATFORM_LABELS = {
    "wallstbots": "WALL ST. BOTS",
    "bitbot13":   "CRYPTO",
    "lvl13":      "AI & QUANTUM",
}

# Bot colours (kept for pick tables)
BOT_COLORS = {
    "bot13":     {"bg": "#ec4899", "abbr": "B13"},
    "oracle":    {"bg": "#a855f7", "abbr": "OR"},
    "wizard":    {"bg": "#10b981", "abbr": "WZ"},
    "equalizer": {"bg": "#00d4ff", "abbr": "EQ"},
    "titan":     {"bg": "#ff8c00", "abbr": "TI"},
}

SIGNAL_CONFIG = {
    "STRONG BUY":  {"color": "#00e676", "border": "#00562b", "bg": "rgba(0,230,118,0.08)"},
    "BUY":         {"color": "#00e676", "border": "#00562b", "bg": "rgba(0,230,118,0.06)"},
    "HOLD":        {"color": "#ffaa00", "border": "#554400", "bg": "rgba(255,170,0,0.06)"},
    "SELL":        {"color": "#ff4457", "border": "#550015", "bg": "rgba(255,68,87,0.06)"},
    "STRONG SELL": {"color": "#ff4457", "border": "#550015", "bg": "rgba(255,68,87,0.10)"},
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


# ── Terminal visual helpers ────────────────────────────────────────────────────

def _mkt_status() -> tuple[str, str]:
    """Return (label, color) based on UTC time (emails send ~9-10 AM ET)."""
    if datetime.utcnow().weekday() >= 5:
        return "MKT CLOSED", "#3a4a5e"
    return "MKT OPEN", "#00e676"


def _signal_pill(action: str) -> str:
    s = SIGNAL_CONFIG.get(action.upper(), SIGNAL_CONFIG["HOLD"])
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'background:{s["bg"]};color:{s["color"]};border:1px solid {s["border"]};'
        f'font-size:10px;font-weight:700;letter-spacing:1px;white-space:nowrap;'
        f'font-family:\'Courier New\',monospace;text-transform:uppercase;">'
        f'{action.upper()}</span>'
    )


def _signal_summary_bar(signals: list[dict]) -> str:
    buy  = sum(1 for s in signals if s.get("action","").upper() in ("BUY","STRONG BUY"))
    hold = sum(1 for s in signals if s.get("action","").upper() == "HOLD")
    sell = sum(1 for s in signals if s.get("action","").upper() in ("SELL","STRONG SELL"))
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;border-collapse:collapse;">
  <tr>
    <td width="33%" style="padding:0 3px 0 0;">
      <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #00562b;border-radius:8px;overflow:hidden;">
        <tr><td bgcolor="#06080d" align="center" style="background-color:#06080d;padding:10px 4px;">
          <div style="font-family:'Courier New',monospace;font-size:22px;font-weight:900;color:#00e676;line-height:1;">{buy}</div>
          <div style="font-family:'Courier New',monospace;font-size:9px;color:#006635;letter-spacing:2px;margin-top:3px;">BUY</div>
        </td></tr>
      </table>
    </td>
    <td width="33%" style="padding:0 2px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #554400;border-radius:8px;overflow:hidden;">
        <tr><td bgcolor="#06080d" align="center" style="background-color:#06080d;padding:10px 4px;">
          <div style="font-family:'Courier New',monospace;font-size:22px;font-weight:900;color:#ffaa00;line-height:1;">{hold}</div>
          <div style="font-family:'Courier New',monospace;font-size:9px;color:#886600;letter-spacing:2px;margin-top:3px;">HOLD</div>
        </td></tr>
      </table>
    </td>
    <td width="33%" style="padding:0 0 0 3px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #550015;border-radius:8px;overflow:hidden;">
        <tr><td bgcolor="#06080d" align="center" style="background-color:#06080d;padding:10px 4px;">
          <div style="font-family:'Courier New',monospace;font-size:22px;font-weight:900;color:#ff4457;line-height:1;">{sell}</div>
          <div style="font-family:'Courier New',monospace;font-size:9px;color:#880020;letter-spacing:2px;margin-top:3px;">SELL</div>
        </td></tr>
      </table>
    </td>
  </tr>
</table>"""


def _decision_card(decision: str, platform_label: str,
                   confidence=None, target=None, rationale: str = "") -> str:
    d = decision.upper()
    if d in ("BUY", "STRONG BUY", "TRADE"):
        d_color, d_border, d_bg = "#00e676", "#00562b", "rgba(0,230,118,0.08)"
        t_color = "#00d4ff"
        display = "BUY"
    elif d in ("SELL", "STRONG SELL"):
        d_color, d_border, d_bg = "#ff4457", "#550015", "rgba(255,68,87,0.08)"
        t_color = "#ff4457"
        display = d
    else:
        d_color, d_border, d_bg = "#ffaa00", "#554400", "rgba(255,170,0,0.08)"
        t_color = "#ffaa00"
        display = "HOLD"

    conf_str   = f"{confidence}%" if confidence is not None else "&mdash;"
    target_str = str(target)      if target     is not None else "&mdash;"
    tc         = t_color          if target     is not None else "#3a4a5e"

    rationale_row = ""
    if rationale:
        rationale_row = f"""
  <tr>
    <td bgcolor="#0d1117" colspan="4" style="background-color:#0d1117;padding:10px 16px 14px;border-top:1px solid #151d2b;">
      <p style="font-size:12px;color:#7d8590;line-height:1.6;margin:0;">{rationale[:280]}</p>
    </td>
  </tr>"""

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2533;border-radius:10px;overflow:hidden;margin-bottom:16px;border-collapse:collapse;">
  <tr>
    <td bgcolor="#06080d" colspan="4" style="background-color:#06080d;padding:10px 16px 8px;border-bottom:1px solid #151d2b;">
      <span style="font-family:'Courier New',monospace;font-size:9px;color:#3a4a5e;letter-spacing:2px;">BOT13 DECISION &middot; {platform_label}</span>
    </td>
  </tr>
  <tr>
    <td bgcolor="#0d1117" style="background-color:#0d1117;padding:14px 16px;vertical-align:middle;">
      <div style="display:inline-block;background:{d_bg};border:1px solid {d_border};border-radius:8px;padding:8px 16px;">
        <span style="font-family:'Courier New',monospace;font-size:24px;font-weight:900;color:{d_color};letter-spacing:2px;">{display}</span>
      </div>
    </td>
    <td bgcolor="#0d1117" style="background-color:#0d1117;padding:14px 12px;text-align:center;vertical-align:middle;">
      <div style="font-family:'Courier New',monospace;font-size:9px;color:#3a4a5e;letter-spacing:1px;margin-bottom:3px;">CONFIDENCE</div>
      <div style="font-family:'Courier New',monospace;font-size:18px;font-weight:700;color:#e6edf3;line-height:1;">{conf_str}</div>
    </td>
    <td bgcolor="#0d1117" style="background-color:#0d1117;padding:14px 12px;text-align:center;vertical-align:middle;">
      <div style="font-family:'Courier New',monospace;font-size:9px;color:#3a4a5e;letter-spacing:1px;margin-bottom:3px;">30D TARGET</div>
      <div style="font-family:'Courier New',monospace;font-size:18px;font-weight:700;color:{tc};line-height:1;">{target_str}</div>
    </td>
    <td bgcolor="#0d1117" style="background-color:#0d1117;padding:14px 16px;"></td>
  </tr>{rationale_row}
</table>"""


def _terminal_signal_row(symbol: str, action: str,
                          chg_pct=None, score=None, company: str = "") -> str:
    s = SIGNAL_CONFIG.get(action.upper(), SIGNAL_CONFIG["HOLD"])
    if chg_pct is not None:
        try:
            v = float(chg_pct)
            chg_str   = f"+{v:.1f}%" if v > 0 else f"{v:.1f}%"
            chg_color = "#00e676" if v > 0 else "#ff4457" if v < 0 else "#3a4a5e"
        except (TypeError, ValueError):
            chg_str, chg_color = str(chg_pct), "#3a4a5e"
    else:
        chg_str, chg_color = "&mdash;", "#3a4a5e"

    score_str = str(int(score)) if score is not None else "&mdash;"
    co_line   = (f'<div style="font-size:10px;color:#3a4a5e;margin-top:1px;">{company[:16]}</div>'
                 if company else "")
    pill = (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'background:{s["bg"]};color:{s["color"]};border:1px solid {s["border"]};'
        f'font-size:10px;font-weight:700;letter-spacing:1px;white-space:nowrap;'
        f'font-family:\'Courier New\',monospace;">{action.upper()}</span>'
    )
    return f"""
<tr>
  <td style="padding:8px 10px;border-bottom:1px solid #0f1520;">
    <div style="font-family:'Courier New',monospace;font-size:13px;font-weight:700;color:#e6edf3;">{symbol}</div>
    {co_line}
  </td>
  <td style="padding:8px 10px;border-bottom:1px solid #0f1520;white-space:nowrap;">{pill}</td>
  <td style="padding:8px 10px;border-bottom:1px solid #0f1520;text-align:right;white-space:nowrap;">
    <span style="font-family:'Courier New',monospace;font-size:11px;color:{chg_color};">{chg_str}</span>
  </td>
  <td style="padding:8px 10px;border-bottom:1px solid #0f1520;text-align:right;white-space:nowrap;">
    <span style="font-family:'Courier New',monospace;font-size:11px;color:#e6edf3;">{score_str}</span>
  </td>
</tr>"""


def _terminal_signals_table(signals: list[dict], max_rows: int = 8) -> str:
    if not signals:
        return '<p style="font-family:\'Courier New\',monospace;font-size:10px;color:#3a4a5e;margin:8px 0;letter-spacing:1px;">NO SIGNALS TODAY</p>'
    rows = ""
    for s in signals[:max_rows]:
        chg     = s.get("change_pct") or s.get("pct_change") or s.get("change")
        score   = s.get("score") or s.get("signal_score")
        company = s.get("company") or s.get("name") or ""
        rows   += _terminal_signal_row(s.get("symbol",""), s.get("action","HOLD"), chg, score, company)
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2533;border-radius:8px;overflow:hidden;border-collapse:collapse;margin-bottom:14px;">
  <tr bgcolor="#0d1117">
    <th style="padding:7px 10px;text-align:left;font-family:'Courier New',monospace;font-size:9px;color:#3a4a5e;letter-spacing:1px;font-weight:700;border-bottom:1px solid #151d2b;">TICKER</th>
    <th style="padding:7px 10px;text-align:left;font-family:'Courier New',monospace;font-size:9px;color:#3a4a5e;letter-spacing:1px;font-weight:700;border-bottom:1px solid #151d2b;">SIGNAL</th>
    <th style="padding:7px 10px;text-align:right;font-family:'Courier New',monospace;font-size:9px;color:#3a4a5e;letter-spacing:1px;font-weight:700;border-bottom:1px solid #151d2b;">CHG%</th>
    <th style="padding:7px 10px;text-align:right;font-family:'Courier New',monospace;font-size:9px;color:#3a4a5e;letter-spacing:1px;font-weight:700;border-bottom:1px solid #151d2b;">SCR</th>
  </tr>
  {rows}
</table>"""


def _portfolio_tiles(signals: list[dict], accent: str = "#00d4ff") -> str:
    if not signals:
        return ""
    tiles = signals[:9]
    row_cells, rows_html = [], ""
    for s in tiles:
        action = s.get("action", "HOLD").upper()
        cfg    = SIGNAL_CONFIG.get(action, SIGNAL_CONFIG["HOLD"])
        sym    = s.get("symbol", "?")
        score  = s.get("score") or s.get("signal_score")
        sc_str = f" &middot; {int(score)}" if score is not None else ""
        row_cells.append(
            f'<td width="33%" style="padding:3px;vertical-align:top;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {accent}25;border-radius:8px;overflow:hidden;">'
            f'<tr><td bgcolor="#0a0e16" align="center" style="background-color:#0a0e16;padding:9px 4px;">'
            f'<div style="font-family:\'Courier New\',monospace;font-size:12px;font-weight:700;color:{accent};">{sym}</div>'
            f'<div style="font-family:\'Courier New\',monospace;font-size:9px;color:{cfg["color"]};margin-top:3px;letter-spacing:1px;">{action}{sc_str}</div>'
            f'</td></tr></table></td>'
        )
        if len(row_cells) == 3:
            rows_html += f"<tr>{''.join(row_cells)}</tr>"
            row_cells = []
    if row_cells:
        while len(row_cells) < 3:
            row_cells.append('<td width="33%" style="padding:3px;"></td>')
        rows_html += f"<tr>{''.join(row_cells)}</tr>"
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:14px;">
  {rows_html}
</table>"""


def _picks_table(picks: list[dict], bot_key: str = "bot13") -> str:
    if not picks:
        return ""
    c    = BOT_COLORS.get(bot_key, BOT_COLORS["bot13"])
    rows = ""
    for p in picks:
        alloc  = f"{p['weight']*100:.0f}%" if p.get("weight") is not None else "&mdash;"
        thesis = (p.get("rationale") or "")[:110]
        rows  += (
            f'<tr><td style="padding:8px 12px;border-bottom:1px solid #151d2b;font-family:\'Courier New\',monospace;'
            f'font-size:13px;font-weight:700;color:#e6edf3;white-space:nowrap;">{p.get("symbol","")}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #151d2b;font-family:\'Courier New\',monospace;'
            f'font-size:12px;font-weight:700;color:{c["bg"]};text-align:right;white-space:nowrap;">{alloc}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #151d2b;font-size:11px;color:#7d8590;">{thesis}</td></tr>'
        )
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e2533;border-radius:8px;overflow:hidden;border-collapse:collapse;margin-bottom:14px;">
  <tr bgcolor="#0d1117">
    <th style="padding:7px 12px;text-align:left;font-family:'Courier New',monospace;font-size:9px;color:#3a4a5e;letter-spacing:1px;font-weight:700;border-bottom:1px solid #151d2b;">SYMBOL</th>
    <th style="padding:7px 12px;text-align:right;font-family:'Courier New',monospace;font-size:9px;color:#3a4a5e;letter-spacing:1px;font-weight:700;border-bottom:1px solid #151d2b;">ALLOC</th>
    <th style="padding:7px 12px;text-align:left;font-family:'Courier New',monospace;font-size:9px;color:#3a4a5e;letter-spacing:1px;font-weight:700;border-bottom:1px solid #151d2b;">THESIS</th>
  </tr>
  {rows}
</table>"""


def _section_label(text: str) -> str:
    return (
        f'<div style="font-family:\'Courier New\',monospace;font-size:9px;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:2px;color:#3a4a5e;margin:14px 0 8px;">{text}</div>'
    )


def _section_divider(platform: str, label_override: str = "") -> str:
    color = PLATFORM_COLORS.get(platform, "#00d4ff")
    label = label_override or SITE_NAMES.get(platform, platform).upper()
    url   = SITE_URLS.get(platform, "#")
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0 14px;border-collapse:collapse;">
  <tr><td style="border-top:1px solid #151d2b;padding-top:16px;">
    <a href="{url}" style="text-decoration:none;">
      <span style="font-family:'Courier New',monospace;font-size:9px;font-weight:700;color:{color};
        letter-spacing:2px;border-left:2px solid {color};padding-left:8px;">{label}</span>
    </a>
  </td></tr>
</table>"""


def _dashboard_link(platform: str) -> str:
    url  = SITE_URLS.get(platform, "#")
    name = SITE_NAMES.get(platform, platform).upper()
    return (
        f'<div style="text-align:right;margin:6px 0 4px;">'
        f'<a href="{url}/dashboard.html" style="font-family:\'Courier New\',monospace;'
        f'font-size:10px;color:#00d4ff;text-decoration:none;letter-spacing:1px;">VIEW {name} DASHBOARD &rarr;</a></div>'
    )


def _cta_button(url: str, text: str) -> str:
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:24px;">
  <tr><td align="center">
    <a href="{url}" style="display:inline-block;background:#001e28;border:1px solid #00d4ff;
      color:#00d4ff;border-radius:8px;padding:12px 28px;font-family:'Courier New',monospace;
      font-size:12px;font-weight:700;text-decoration:none;letter-spacing:1px;">{text} &rarr;</a>
  </td></tr>
</table>"""


def _portfolio_section(recipient: dict) -> str:
    """Render portfolio signal tiles across enabled platforms only."""
    blocks = []
    config = [
        ("wallstbots", "STOCKS",     "#00d4ff"),
        ("bitbot13",   "CRYPTO",     "#ff4457"),
        ("lvl13",      "AI/QUANTUM", "#a855f7"),
    ]
    for plat, label, accent in config:
        if not recipient.get(f"email_{plat}", True):
            continue
        signals = recipient.get(f"portfolio_signals_{plat}", [])
        if not signals:
            continue
        blocks.append(_section_label(f"{label} SIGNALS"))
        blocks.append(_portfolio_tiles(signals, accent))
    if not blocks:
        return ('<p style="font-family:\'Courier New\',monospace;font-size:11px;'
                'color:#3a4a5e;margin:0 0 12px;letter-spacing:1px;">NO PORTFOLIO MATCHES TODAY</p>')
    return "".join(blocks)


# ── Email shell wrappers ───────────────────────────────────────────────────────
_STYLE_BLOCK = """
<style type="text/css">
  body,.em-body{background-color:#06080d !important;color:#e6edf3 !important;}
  u+.em-body{background-color:#06080d !important;}
  [data-ogsc] .em-body,[data-ogsb] .em-body{background-color:#06080d !important;}
  .em-wrap,.em-center{background-color:#06080d !important;}
</style>"""


def _header_td(logo_html: str, date_str: str, time_str: str) -> str:
    mkt_label, mkt_color = _mkt_status()
    return f"""
      <tr>
        <td bgcolor="#06080d" style="background-color:#06080d;padding:14px 20px;
          border:1px solid #1e2533;border-bottom:1px solid #151d2b;border-radius:12px 12px 0 0;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="vertical-align:middle;">
                <div style="font-family:'Courier New',monospace;font-size:15px;font-weight:700;
                  color:#00d4ff;letter-spacing:3px;">{logo_html}</div>
                <div style="font-family:'Courier New',monospace;font-size:10px;color:#3a4a5e;
                  margin-top:3px;letter-spacing:1px;">{date_str} &nbsp;&bull;&nbsp; {time_str}</div>
              </td>
              <td align="right" style="vertical-align:middle;">
                <span style="font-family:'Courier New',monospace;font-size:10px;
                  color:{mkt_color};letter-spacing:1px;">&#9679; {mkt_label}</span>
              </td>
            </tr>
          </table>
        </td>
      </tr>"""


def _footer_td(site_name: str, site_url: str, year: int, extra_links: str = "") -> str:
    return f"""
      <tr>
        <td bgcolor="#06080d" style="background-color:#06080d;border:1px solid #1e2533;
          border-top:none;padding:16px 20px;border-radius:0 0 12px 12px;">
          <p style="font-family:'Courier New',monospace;font-size:10px;color:#253040;margin:0 0 6px;line-height:1.6;">
            You're receiving this because you're subscribed to {site_name}.
          </p>
          {extra_links}
          <p style="font-size:10px;margin:0;">
            <a href="{site_url}/dashboard.html#email-prefs"
              style="color:#00d4ff30;text-decoration:none;font-family:'Courier New',monospace;">Email Preferences</a>
            &nbsp;&nbsp;&bull;&nbsp;&nbsp;
            <span style="color:#253040;font-family:'Courier New',monospace;">&copy; {year} {site_name}</span>
          </p>
        </td>
      </tr>"""


def _wrap(platform: str, preheader: str, body_html: str) -> str:
    site_name = SITE_NAMES.get(platform, "WallStBots")
    site_url  = SITE_URLS.get(platform, "https://wallstbots.tech")
    year      = datetime.now().year
    now       = datetime.now()
    date_str  = now.strftime("%b %d, %Y").upper()
    time_str  = now.strftime("%H:%M ET")
    logos = {
        "wallstbots": "WALL ST. BOTS",
        "bitbot13":   "BITBOT13",
        "lvl13":      "LEVEL XIII",
    }
    logo = logos.get(platform, site_name.upper())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="dark light"/>
<meta name="supported-color-schemes" content="dark light"/>
<title>{site_name}</title>
{_STYLE_BLOCK}
</head>
<body bgcolor="#06080d" style="margin:0;padding:0;background-color:#06080d !important;-webkit-font-smoothing:antialiased;">
<div class="em-body" style="background-color:#06080d !important;">
<span style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</span>
<table class="em-wrap" width="100%" cellpadding="0" cellspacing="0" bgcolor="#06080d"
  style="background-color:#06080d !important;padding:20px 0 40px;">
  <tr><td class="em-center" align="center" bgcolor="#06080d"
    style="background-color:#06080d !important;padding:0 12px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">
      {_header_td(logo, date_str, time_str)}
      <tr>
        <td bgcolor="#0d1117" style="background-color:#0d1117 !important;
          border-left:1px solid #1e2533;border-right:1px solid #1e2533;padding:20px;">
          {body_html}
        </td>
      </tr>
      {_footer_td(site_name, site_url, year)}
    </table>
  </td></tr>
</table>
</div>
</body>
</html>"""


def _wrap_consolidated(preheader: str, body_html: str) -> str:
    year     = datetime.now().year
    now      = datetime.now()
    date_str = now.strftime("%b %d, %Y").upper()
    time_str = now.strftime("%H:%M ET")
    extra_links = """
          <p style="font-size:10px;margin:0 0 6px;">
            <a href="https://wallstbots.tech" style="color:#00d4ff40;text-decoration:none;font-family:'Courier New',monospace;">WallStBots</a>
            &nbsp;&bull;&nbsp;
            <a href="https://bitbot13.tech" style="color:#00d4ff40;text-decoration:none;font-family:'Courier New',monospace;">BitBot13</a>
            &nbsp;&bull;&nbsp;
            <a href="https://lvl13.tech" style="color:#00d4ff40;text-decoration:none;font-family:'Courier New',monospace;">Level XIII</a>
          </p>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="dark light"/>
<meta name="supported-color-schemes" content="dark light"/>
<title>Wall St. Bots — Daily Report</title>
{_STYLE_BLOCK}
</head>
<body bgcolor="#06080d" style="margin:0;padding:0;background-color:#06080d !important;-webkit-font-smoothing:antialiased;">
<div class="em-body" style="background-color:#06080d !important;">
<span style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</span>
<table class="em-wrap" width="100%" cellpadding="0" cellspacing="0" bgcolor="#06080d"
  style="background-color:#06080d !important;padding:20px 0 40px;">
  <tr><td class="em-center" align="center" bgcolor="#06080d"
    style="background-color:#06080d !important;padding:0 12px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">
      {_header_td("WALL ST. BOTS", date_str, time_str)}
      <tr>
        <td bgcolor="#0d1117" style="background-color:#0d1117 !important;
          border-left:1px solid #1e2533;border-right:1px solid #1e2533;padding:20px;">
          {body_html}
        </td>
      </tr>
      {_footer_td("Wall St. Bots", "https://wallstbots.tech", year, extra_links)}
    </table>
  </td></tr>
</table>
</div>
</body>
</html>"""


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

    sections = []

    if site_signals:
        sections.append(_signal_summary_bar(site_signals))

    sections.append(_decision_card(
        decision, PLATFORM_LABELS.get(platform, platform.upper()),
        confidence, target, rationale,
    ))

    if picks and decision in ("TRADE", "BUY", "STRONG BUY"):
        sections.append(_section_label("POSITIONS"))
        sections.append(_picks_table(picks[:6], "bot13"))

    actionable = [s for s in site_signals
                  if s.get("action","").upper() in ("STRONG BUY","BUY","SELL","STRONG SELL")][:8]
    if actionable:
        sections.append(_section_label("TOP SIGNALS"))
        sections.append(_terminal_signals_table(actionable))

    port_signals = recipient.get("portfolio_signals", [])
    if port_signals:
        sections.append(_section_label("YOUR PORTFOLIO"))
        sections.append(_portfolio_tiles(port_signals, PLATFORM_COLORS.get(platform, "#00d4ff")))

    sections.append(_cta_button(f"{SITE_URLS[platform]}/dashboard.html", "OPEN DASHBOARD"))

    preheader = f"BOT13: {decision} · {len(actionable)} signals · {today_str}"
    return _wrap(platform, preheader, "\n".join(sections))


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

    preheader = f"BOT13 {decision} — {today_str}"
    sections  = [
        _decision_card(decision, PLATFORM_LABELS.get(platform, platform.upper()),
                       confidence, target, rationale),
    ]
    if picks:
        sections.append(_section_label("POSITIONS ENTERED"))
        sections.append(_picks_table(picks, "bot13"))
    sections.append(_cta_button(f"{SITE_URLS[platform]}/dashboard.html", "VIEW DASHBOARD"))

    return _wrap(platform, preheader, "\n".join(sections))


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 3 — Weekly Picks (ORACLE)
# ═══════════════════════════════════════════════════════════════════
def build_weekly_email(
    platform: str,
    oracle_strategy: dict,
    leaderboard: list[dict],
    recipient: dict,
) -> str:
    today_str = date.today().strftime("%B %d, %Y")
    week      = oracle_strategy.get("week", str(date.today()))
    decision  = oracle_strategy.get("decision", "HOLD")
    rationale = oracle_strategy.get("rationale", "")
    picks     = oracle_strategy.get("picks", [])
    confidence = oracle_strategy.get("confidence")

    sections = [
        _section_label(f"ORACLE — WEEK OF {week.upper()}"),
        _decision_card(decision, PLATFORM_LABELS.get(platform, platform.upper()),
                       confidence, None, rationale),
    ]
    if picks:
        sections.append(_section_label("THIS WEEK'S POSITIONS"))
        sections.append(_picks_table(picks, "oracle"))
    else:
        sections.append('<p style="font-size:12px;color:#3a4a5e;margin:8px 0;">Oracle is holding cash this week.</p>')

    sections.append(_cta_button(f"{SITE_URLS[platform]}/dashboard.html", "TRACK PERFORMANCE"))
    preheader = f"Oracle weekly picks — {len(picks)} positions · {today_str}"
    return _wrap(platform, preheader, "\n".join(sections))


# ═══════════════════════════════════════════════════════════════════
# EMAIL TEMPLATE 4 — Monthly Picks (WIZARD)
# ═══════════════════════════════════════════════════════════════════
def build_monthly_email(
    platform: str,
    wizard_strategy: dict,
    leaderboard: list[dict],
    recipient: dict,
) -> str:
    month     = date.today().strftime("%B %Y")
    today_str = date.today().strftime("%B %d, %Y")
    decision  = wizard_strategy.get("decision", "HOLD")
    rationale = wizard_strategy.get("rationale", "")
    picks     = wizard_strategy.get("picks", [])
    confidence = wizard_strategy.get("confidence")

    sections = [
        _section_label(f"WIZARD — {month.upper()}"),
        _decision_card(decision, PLATFORM_LABELS.get(platform, platform.upper()),
                       confidence, None, rationale),
    ]
    if picks:
        sections.append(_section_label("THIS MONTH'S POSITIONS"))
        sections.append(_picks_table(picks, "wizard"))
    else:
        sections.append('<p style="font-size:12px;color:#3a4a5e;margin:8px 0;">Wizard is holding current positions.</p>')

    sections.append(_cta_button(f"{SITE_URLS[platform]}/dashboard.html", "VIEW FULL REPORT"))
    preheader = f"Wizard monthly portfolio — {month} · {len(picks)} positions"
    return _wrap(platform, preheader, "\n".join(sections))


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
    preheader = f"BOT13 Daily Report — {today_str}"

    show_portfolio  = recipient.get("email_portfolio",  True)
    show_wallstbots = recipient.get("email_wallstbots", True)
    show_bitbot13   = recipient.get("email_bitbot13",   True)
    show_lvl13      = recipient.get("email_lvl13",      True)

    sections = []

    # Combined BUY/HOLD/SELL summary bar from all fresh enabled platforms
    all_signals: list[dict] = []
    for plat, enabled in [("wallstbots", show_wallstbots),
                           ("bitbot13",   show_bitbot13),
                           ("lvl13",      show_lvl13)]:
        if enabled:
            pd = platform_data.get(plat, {})
            if pd.get("is_fresh", True):
                all_signals.extend(pd.get("signals", []))
    if all_signals:
        sections.append(_signal_summary_bar(all_signals))

    # Per-platform sections
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

        sections.append(_section_divider(plat))

        if not is_fresh:
            sections.append(
                f'<p style="font-family:\'Courier New\',monospace;font-size:10px;color:#3a4a5e;'
                f'margin:8px 0 16px;letter-spacing:1px;">MKT CLOSED &mdash; '
                f'<a href="{site_url}/dashboard.html" style="color:#00d4ff;text-decoration:none;">'
                f'VIEW LAST UPDATE &rarr;</a></p>'
            )
            continue

        bot13_data = funds.get("bot13") or funds.get("BOT13") or {}
        strategy   = bot13_data.get("strategy") or bot13_data
        decision   = strategy.get("decision", "HOLD")
        rationale  = strategy.get("rationale", "")
        picks      = strategy.get("picks", [])
        confidence = strategy.get("confidence")
        target     = strategy.get("target") or strategy.get("price_target")

        sections.append(_decision_card(
            decision, PLATFORM_LABELS[plat], confidence, target, rationale
        ))

        if picks and decision in ("TRADE", "BUY", "STRONG BUY"):
            sections.append(_section_label("POSITIONS"))
            sections.append(_picks_table(picks, "bot13"))

        if signals:
            actionable = [s for s in signals
                          if s.get("action","").upper() in ("STRONG BUY","BUY","SELL","STRONG SELL")][:6]
            display = actionable if actionable else signals[:6]
            sections.append(_section_label("TOP SIGNALS"))
            sections.append(_terminal_signals_table(display))

        if is_weekly:
            oracle_d = funds.get("oracle") or funds.get("ORACLE") or {}
            oracle_s = oracle_d.get("strategy") or oracle_d
            o_picks  = oracle_s.get("picks", [])
            if o_picks:
                sections.append(_section_label("ORACLE — WEEKLY PICKS"))
                sections.append(_picks_table(o_picks, "oracle"))

        if is_monthly:
            wizard_d = funds.get("wizard") or funds.get("WIZARD") or {}
            wizard_s = wizard_d.get("strategy") or wizard_d
            w_picks  = wizard_s.get("picks", [])
            if w_picks:
                sections.append(_section_label("WIZARD — MONTHLY PORTFOLIO"))
                sections.append(_picks_table(w_picks, "wizard"))

        sections.append(_dashboard_link(plat))

    # Portfolio section
    if show_portfolio:
        has_any = any(
            recipient.get(f"portfolio_signals_{p}", [])
            for p in ("wallstbots", "bitbot13", "lvl13")
            if recipient.get(f"email_{p}", True)
        )
        if has_any:
            sections.append(f"""
<table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0 14px;border-collapse:collapse;">
  <tr><td style="border-top:1px solid #151d2b;padding-top:16px;">
    <span style="font-family:'Courier New',monospace;font-size:9px;font-weight:700;
      color:#facc15;letter-spacing:2px;border-left:2px solid #facc15;padding-left:8px;">YOUR PORTFOLIO</span>
  </td></tr>
</table>""")
            sections.append(_portfolio_section(recipient))

    if not any([show_portfolio, show_wallstbots, show_bitbot13, show_lvl13]):
        sections.append(
            '<p style="font-family:\'Courier New\',monospace;font-size:11px;color:#3a4a5e;'
            'margin:20px 0;letter-spacing:1px;">NO SECTIONS ENABLED &mdash; '
            '<a href="https://wallstbots.tech/dashboard.html#email-prefs" '
            'style="color:#00d4ff;text-decoration:none;">UPDATE PREFERENCES &rarr;</a></p>'
        )

    return _wrap_consolidated(preheader, "\n".join(sections))
