#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_news.py -- per-platform financial news, scoped to each site's assets.

Pulls headlines from NewsAPI.org relevant to the ASSETS TRADED ON EACH PLATFORM,
dedupes, tags each story with the universe tickers it mentions, and pushes the feed
to the backend per platform (which the public page + member pages read).

  public page -> shows the platform's asset-relevant feed (scoped by the queries below)
  member page -> filters that feed down to the member's own holdings (frontend already
                 does this via each story's tickers[] / title match)

Security: the NewsAPI key lives only server-side (secrets.json / GitHub secret) and never
reaches the browser -- sites read the pre-fetched backend feed.

Usage:
  python Project/scripts/refresh_news.py --platform {wallstbots,aistocks,bitbot13}
Config from secrets.json OR env (NEWSAPI_KEY, BACKEND_URL, INTERNAL_API_KEY).
NewsAPI free tier = 100 req/day; each platform run uses ~5.
"""
import json, os, re, sys
import datetime as dt
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing requests. pip install requests"); sys.exit(1)

ROOT    = Path(__file__).resolve().parents[2]
SECRETS = ROOT / "Project" / "config" / "secrets.json"

def _cfg(key_secret, key_env, default=""):
    try:
        s = json.loads(SECRETS.read_text()) if SECRETS.exists() else {}
    except Exception:
        s = {}
    return s.get(key_secret) or os.environ.get(key_env, default)

NEWSAPI_KEY  = _cfg("newsapi_key",      "NEWSAPI_KEY")
BACKEND_URL  = (_cfg("api_url",         "BACKEND_URL")).rstrip("/")
INTERNAL_KEY = _cfg("internal_api_key", "INTERNAL_API_KEY")

UNIVERSES = {
    "wallstbots": ['XOM','CVX','COP','FANG','OKLO','LIN','SHW','FCX','APD','ALB','CAT','RTX',
        'HON','GE','SPCX','AMZN','TSLA','HD','IBTA','BIRK','WMT','PG','COST','CART','KR','LLY',
        'JNJ','UNH','GRAL','SMMT','BRK.B','JPM','V','SOFI','AFRM','NVDA','AAPL','MSFT','ARM',
        'ALAB','RBRK','GOOGL','META','NFLX','RDDT','SPOT','NEE','SO','DUK','VST','PLD','WELL',
        'AMT','LINE','EQIX'],
    "aistocks": ['NVDA','AMD','INTC','ARM','ALAB','MRVL','AVGO','QCOM','SMCI','CRDO','MU','NVTS',
        'MSFT','GOOGL','META','AMZN','ORCL','CRM','NOW','SNOW','DDOG','NET','ZS','OKTA','PATH',
        'PLTR','AI','BBAI','SOUN','UPST','RBRK','PANW','ANET','PSTG','TSLA','ISRG','RXRX','GRAL',
        'SMMT','IONQ','RGTI','QBTS','QUBT','ARQQ','IBM','XNDU','INFQ','HQ','CBRS','SPCX'],
    "bitbot13": ['BTC','ETH','BNB','SOL','XRP','ADA','TON','AVAX','DOGE','TRX','LINK','DOT','SHIB',
        'BCH','NEAR','UNI','LTC','APT','SUI','ATOM','ICP','FIL','ARB','AAVE','OP','ETC','VET','INJ',
        'ALGO','XLM','HBAR','MKR','JUP','RENDER','FET','ONDO','WIF','RUNE','QNT','KAS','THETA','WLD',
        'SEI','EGLD','CRV','MANTA','PEPE','FLOKI','PENDLE','NOT'],
}

TAG_STOPLIST = {"AI","ALL","ON","IT","SO","V","GE","HD","HQ","NET","NOW","ARM","CART","KR",
                "TON","SUI","SEI","NOT","WIF","OP","UNI","VET","ICP","AMT","PLD","LINE","INJ"}

PLATFORM_QUERIES = {
    "wallstbots": {
        "Energy":      '(Exxon OR Chevron OR ConocoPhillips OR "oil price" OR LNG OR "natural gas" OR OKLO OR "nuclear power") AND (stock OR earnings OR shares OR investor)',
        "Materials":   '(Linde OR "Sherwin-Williams" OR Freeport OR Albemarle OR lithium OR copper OR "industrial metals") AND (stock OR earnings OR price OR shares)',
        "Industrials": '(Caterpillar OR Raytheon OR Honeywell OR "General Electric" OR defense OR aerospace OR industrials) AND (stock OR earnings OR contract OR shares)',
        "Consumer":    '(Amazon OR Tesla OR Walmart OR Costco OR "Home Depot" OR "Procter Gamble" OR retail OR consumer) AND (stock OR earnings OR sales OR shares)',
        "Healthcare":  '("Eli Lilly" OR "Johnson Johnson" OR UnitedHealth OR biotech OR "drug approval" OR healthcare) AND (stock OR earnings OR FDA OR shares)',
        "Financials":  '(JPMorgan OR Visa OR "Berkshire Hathaway" OR SoFi OR "Federal Reserve" OR "interest rate" OR "S&P 500") AND (stock OR market OR earnings OR investor)',
        "Big Tech":    '(Nvidia OR Apple OR Microsoft OR Alphabet OR Google OR Meta OR Netflix OR ARM) AND (stock OR earnings OR shares OR AI)',
    },
    "aistocks": {
        "AI Chips":    '(Nvidia OR AMD OR Broadcom OR Marvell OR "Super Micro" OR Micron OR "AI chip" OR "data center" OR GPU) AND (stock OR earnings OR shares OR revenue)',
        "AI Software": '(Palantir OR "C3.ai" OR Snowflake OR Datadog OR CrowdStrike OR "Palo Alto" OR "artificial intelligence" OR "AI software") AND (stock OR earnings OR shares)',
        "Quantum":     '("quantum computing" OR IonQ OR Rigetti OR "D-Wave" OR Quantinuum OR qubit OR "quantum processor") AND (stock OR shares OR investor OR breakthrough)',
        "Cloud Data":  '(Microsoft OR Alphabet OR Amazon OR Oracle OR Salesforce OR ServiceNow OR "cloud computing" OR hyperscaler) AND (stock OR earnings OR AI OR shares)',
        "AI Movers":   '("AI stock" OR "artificial intelligence" OR OpenAI OR Anthropic OR "AI bubble" OR "AI trade") AND (stock OR shares OR "Wall Street" OR investor)',
    },
    "bitbot13": {
        "Bitcoin ETH": '(bitcoin OR ethereum OR "BTC price" OR "ETH price" OR "crypto rally" OR "crypto selloff") AND (price OR trading OR market OR investor)',
        "Altcoins":    '(Solana OR Cardano OR XRP OR Avalanche OR Chainlink OR Polkadot OR altcoin OR "layer 2") AND (price OR crypto OR rally OR trading)',
        "Regulation":  '("crypto regulation" OR SEC OR "spot ETF" OR stablecoin OR "digital assets" OR CFTC) AND (crypto OR bitcoin OR ruling OR approval)',
        "DeFi Memes":  '(DeFi OR "decentralized finance" OR Uniswap OR Aave OR Dogecoin OR "meme coin" OR PEPE OR Shiba) AND (crypto OR price OR token OR trading)',
        "Crypto Wire": '("crypto market" OR "digital currency" OR blockchain OR "on-chain") AND (price OR bitcoin OR ethereum OR trading)',
    },
}

EXCLUDE = ["pypi.org","github.com","stackoverflow.com","reddit.com","medium.com","dev.to",
           "npmjs.com","ycombinator.com","lobste.rs"]

def _excluded(a):
    url = (a.get("url") or "").lower()
    src = ((a.get("source") or {}).get("name") or "").lower()
    return any(d in url or d.split(".")[0] in src for d in EXCLUDE)

def _tag_tickers(text, universe):
    up = (text or "").upper()
    hits = []
    for t in universe:
        if t in TAG_STOPLIST:
            continue
        if re.search(r'(?<![A-Z0-9])' + re.escape(t) + r'(?![A-Z0-9])', up):
            hits.append(t)
    return hits

def fetch(query, page_size=8):
    frm = (dt.datetime.utcnow() - dt.timedelta(days=3)).strftime("%Y-%m-%d")
    try:
        r = requests.get("https://newsapi.org/v2/everything",
            params={"q": query, "from": frm, "language": "en",
                    "sortBy": "publishedAt", "pageSize": page_size, "apiKey": NEWSAPI_KEY},
            timeout=15)
        if r.status_code == 200:
            return [a for a in r.json().get("articles", []) if a.get("title") and not _excluded(a)]
        print("  HTTP %s: %s" % (r.status_code, r.text[:160]))
    except Exception as e:
        print("  fetch error: %s" % e)
    return []

def run(platform):
    if platform not in PLATFORM_QUERIES:
        print("ERROR: unknown platform '%s'" % platform); sys.exit(1)
    if not NEWSAPI_KEY:
        print("ERROR: no NewsAPI key (secrets.json newsapi_key / env NEWSAPI_KEY)"); sys.exit(1)
    universe = UNIVERSES[platform]
    print("[news] platform=%s -- %d query sets" % (platform, len(PLATFORM_QUERIES[platform])))

    items = []
    for label, q in PLATFORM_QUERIES[platform].items():
        arts = fetch(q, page_size=8)
        print("  %-12s -> %d" % (label, len(arts)))
        for a in arts:
            title = a.get("title", "").split(" - ")[0]
            desc  = a.get("description", "") or ""
            items.append({
                "title":        title,
                "source":       (a.get("source") or {}).get("name", ""),
                "sector":       label,
                "published_at": a.get("publishedAt"),
                "url":          a.get("url", "#"),
                "tickers":      _tag_tickers(title + " " + desc, universe),
            })

    seen, out = set(), []
    for it in sorted(items, key=lambda x: x.get("published_at", ""), reverse=True):
        k = (it["title"] or "")[:80].lower()
        if k in seen:
            continue
        seen.add(k); out.append(it)
    out = out[:30]

    payload = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "sectors":      list(PLATFORM_QUERIES[platform].keys()),
        "items":        out,
    }
    tagged = sum(1 for i in out if i["tickers"])
    print("[news] %s: %d headlines (%d ticker-tagged)" % (platform, len(out), tagged))

    if not BACKEND_URL or not INTERNAL_KEY:
        print("  [push] BACKEND_URL/INTERNAL_API_KEY missing -- not pushed"); return
    try:
        r = requests.post(BACKEND_URL + "/internal/tracker/push",
            json={"data_type": "news", "platform": platform, "data": payload},
            headers={"X-Internal-Key": INTERNAL_KEY}, timeout=20)
        print("  [push] %s news -> HTTP %s" % (platform, r.status_code))
        if r.status_code != 200:
            print("    %s" % r.text[:200])
    except Exception as e:
        print("  [push] error: %s" % e)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", required=True, choices=["wallstbots","aistocks","bitbot13"])
    run(ap.parse_args().platform)
