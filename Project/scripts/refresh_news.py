#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_news.py -- per-platform financial news via Google News RSS (FREE, NO rate limits).

Replaces the NewsAPI version, whose free tier (50 req/12h) blacked the feed out. Google
News RSS has no API key and no request cap, so this is truly set-and-forget.

Usage: python Project/scripts/refresh_news.py --platform {wallstbots,aistocks,bitbot13}
Config from secrets.json OR env (BACKEND_URL/api_url, INTERNAL_API_KEY/internal_api_key).
"""
import json, os, re, sys, urllib.request, urllib.parse
import datetime as dt
from pathlib import Path
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

ROOT    = Path(__file__).resolve().parents[2]
SECRETS = ROOT / "Project" / "config" / "secrets.json"
def _cfg(k_s, k_e, d=""):
    try: s = json.loads(SECRETS.read_text()) if SECRETS.exists() else {}
    except Exception: s = {}
    return s.get(k_s) or os.environ.get(k_e, d)
BACKEND_URL  = (_cfg("api_url", "BACKEND_URL")).rstrip("/")
INTERNAL_KEY = _cfg("internal_api_key", "INTERNAL_API_KEY")

UNIVERSES = {
    "wallstbots": ['XOM','CVX','COP','FANG','OKLO','LIN','SHW','FCX','APD','ALB','CAT','RTX','HON','GE','SPCX','AMZN','TSLA','HD','IBTA','BIRK','WMT','PG','COST','CART','KR','LLY','JNJ','UNH','GRAL','SMMT','BRK.B','JPM','V','SOFI','AFRM','NVDA','AAPL','MSFT','ARM','ALAB','RBRK','GOOGL','META','NFLX','RDDT','SPOT','NEE','SO','DUK','VST','PLD','WELL','AMT','LINE','EQIX'],
    "aistocks": ['NVDA','AMD','INTC','ARM','ALAB','MRVL','AVGO','QCOM','SMCI','CRDO','MU','NVTS','MSFT','GOOGL','META','AMZN','ORCL','CRM','NOW','SNOW','DDOG','NET','ZS','OKTA','PATH','PLTR','AI','BBAI','SOUN','UPST','RBRK','PANW','ANET','PSTG','TSLA','ISRG','RXRX','GRAL','SMMT','IONQ','RGTI','QBTS','QUBT','ARQQ','IBM','XNDU','INFQ','HQ','CBRS','SPCX'],
    "bitbot13": ['BTC','ETH','BNB','SOL','XRP','ADA','TON','AVAX','DOGE','TRX','LINK','DOT','SHIB','BCH','NEAR','UNI','LTC','APT','SUI','ATOM','ICP','FIL','ARB','AAVE','OP','ETC','VET','INJ','ALGO','XLM','HBAR','MKR','JUP','RENDER','FET','ONDO','WIF','RUNE','QNT','KAS','THETA','WLD','SEI','EGLD','CRV','MANTA','PEPE','FLOKI','PENDLE','NOT'],
}
TAG_STOPLIST = {"AI","ALL","ON","IT","SO","V","GE","HD","HQ","NET","NOW","ARM","CART","KR","TON","SUI","SEI","NOT","WIF","OP","UNI","VET","ICP","AMT","PLD","LINE","INJ"}

PLATFORM_QUERIES = {
    "wallstbots": {
        "Energy":      "oil gas energy stocks Exxon Chevron OKLO nuclear",
        "Industrials": "Caterpillar Raytheon Honeywell defense aerospace stocks",
        "Consumer":    "Amazon Tesla Walmart Costco retail stocks earnings",
        "Healthcare":  "Eli Lilly UnitedHealth biotech FDA healthcare stocks",
        "Financials":  "JPMorgan Visa Berkshire Federal Reserve S&P 500 stocks",
        "Big Tech":    "Nvidia Apple Microsoft Google Meta Netflix stock",
    },
    "aistocks": {
        "AI Chips":    "Nvidia AMD Broadcom Micron AI chip data center stock",
        "AI Software": "Palantir Snowflake CrowdStrike Palo Alto AI software stock",
        "Quantum":     "quantum computing IonQ Rigetti D-Wave qubit stock",
        "Cloud Data":  "Microsoft Oracle Salesforce cloud computing AI stock",
        "AI Movers":   "AI stock artificial intelligence OpenAI Wall Street",
    },
    "bitbot13": {
        "Bitcoin ETH": "bitcoin ethereum price crypto market",
        "Altcoins":    "Solana Cardano XRP Avalanche Chainlink altcoin price",
        "Regulation":  "crypto regulation SEC spot ETF stablecoin",
        "DeFi Memes":  "DeFi Uniswap Aave Dogecoin PEPE meme coin crypto",
        "Crypto Wire": "crypto market blockchain digital currency trading",
    },
}
EXCLUDE = ["pypi.org","github.com","stackoverflow.com","reddit.com","medium.com"]

def _tag(text, universe):
    up=(text or "").upper(); hits=[]
    for t in universe:
        if t in TAG_STOPLIST: continue
        if re.search(r'(?<![A-Z0-9])'+re.escape(t)+r'(?![A-Z0-9])', up): hits.append(t)
    return hits

def fetch(query, label, universe):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query + " when:2d", "hl":"en-US","gl":"US","ceid":"US:en"})
    out=[]
    try:
        req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (WallStBots news)"})
        xml=urllib.request.urlopen(req, timeout=20).read()
        root=ET.fromstring(xml)
        for it in root.findall(".//item"):
            title=(it.findtext("title") or "").strip()
            if not title: continue
            link=(it.findtext("link") or "#").strip()
            src_el=it.find("{*}source") or it.find("source")
            source=(src_el.text.strip() if src_el is not None and src_el.text else "")
            if not source and " - " in title:
                source=title.rsplit(" - ",1)[-1].strip(); title=title.rsplit(" - ",1)[0].strip()
            pub=it.findtext("pubDate") or ""
            try: pub_iso=parsedate_to_datetime(pub).astimezone(dt.timezone.utc).isoformat()
            except Exception: pub_iso=dt.datetime.utcnow().isoformat()+"Z"
            if any(d in link.lower() for d in EXCLUDE): continue
            out.append({"title":title,"source":source,"sector":label,"published_at":pub_iso,
                        "url":link,"tickers":_tag(title, universe)})
    except Exception as e:
        print("  fetch error [%s]: %s" % (label, e))
    return out

def run(platform):
    if platform not in PLATFORM_QUERIES:
        print("ERROR unknown platform"); sys.exit(1)
    uni=UNIVERSES[platform]; items=[]
    print("[news] %s -- %d RSS query sets (Google News, no rate limit)" % (platform, len(PLATFORM_QUERIES[platform])))
    for label,q in PLATFORM_QUERIES[platform].items():
        arts=fetch(q,label,uni); print("  %-12s -> %d" % (label,len(arts))); items+=arts
    seen,out=set(),[]
    for it in sorted(items, key=lambda x:x.get("published_at",""), reverse=True):
        k=(it["title"] or "")[:80].lower()
        if k in seen: continue
        seen.add(k); out.append(it)
    out=out[:30]
    payload={"generated_at":dt.datetime.utcnow().isoformat()+"Z","sectors":list(PLATFORM_QUERIES[platform].keys()),"items":out}
    tagged=sum(1 for i in out if i["tickers"])
    print("[news] %s: %d headlines (%d ticker-tagged)" % (platform,len(out),tagged))
    if not BACKEND_URL or not INTERNAL_KEY:
        print("  [push] missing backend/key -- not pushed"); return len(out)
    try:
        req=urllib.request.Request(BACKEND_URL+"/internal/tracker/push",
            data=json.dumps({"data_type":"news","platform":platform,"data":payload}).encode(),
            headers={"X-Internal-Key":INTERNAL_KEY,"Content-Type":"application/json"})
        code=urllib.request.urlopen(req,timeout=20).getcode()
        print("  [push] %s -> HTTP %s" % (platform,code))
    except Exception as e:
        print("  [push] error: %s" % e)
    return len(out)

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--platform",required=True,choices=["wallstbots","aistocks","bitbot13"])
    run(ap.parse_args().platform)
