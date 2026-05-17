#!/usr/bin/env python3
"""
refresh_news.py
Pulls AI/Quantum + sector-tagged headlines from NewsAPI.org,
dedupes, sorts, and writes to public_html/data/news.json.

Run nightly (or every few hours) on the GCP VM, or locally on a schedule.
The site reads news.json — your API key never reaches the browser.

NewsAPI free dev tier: 100 requests/day. We use ~6 per run.
"""
import json
import os
import sys
import datetime as dt
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing requests. Install with: pip install requests")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / "config" / "secrets.json"
OUT_PATH = ROOT / "public_html" / "data" / "news.json"

# Sector → NewsAPI search query
SECTOR_QUERIES = {
    "AI & Quantum": '("artificial intelligence" OR "quantum computing" OR "AI chip" OR "qubit" OR Nvidia OR Anthropic OR OpenAI OR IonQ OR Quantinuum OR Rigetti)',
    "Biotech":      '(biotech OR mRNA OR CRISPR OR "gene therapy" OR "FDA approval" OR clinical OR Moderna OR BioNTech OR Vertex)',
    "Energy":       '(oil OR LNG OR renewables OR solar OR "energy storage" OR Aramco OR Exxon OR Chevron OR "First Solar")',
    "Defense":      '(defense OR Lockheed OR Raytheon OR "Northrop Grumman" OR BAE OR hypersonic OR "missile defense")',
    "Finance":      '(JPMorgan OR Goldman OR "Bank of America" OR Visa OR Mastercard OR "Federal Reserve" OR earnings)',
}

def load_secrets():
    if not SECRETS_PATH.exists():
        print(f"Missing {SECRETS_PATH}. Copy secrets.example.json and fill in keys.")
        sys.exit(1)
    return json.loads(SECRETS_PATH.read_text())

def fetch_sector(api_key, sector, query, page_size=8):
    """Fetch top recent headlines matching the sector query."""
    url = "https://newsapi.org/v2/everything"
    # Last 3 days only, English, sorted by recency
    from_date = (dt.datetime.utcnow() - dt.timedelta(days=3)).strftime("%Y-%m-%d")
    params = {
        "q": query, "from": from_date, "language": "en",
        "sortBy": "publishedAt", "pageSize": page_size, "apiKey": api_key,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return [{
                "title":        a.get("title", "").split(" - ")[0],
                "source":       (a.get("source") or {}).get("name", ""),
                "sector":       sector,
                "published_at": a.get("publishedAt"),
                "url":          a.get("url", "#"),
            } for a in data.get("articles", []) if a.get("title")]
        else:
            print(f"  [{sector}] HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  [{sector}] error: {e}")
    return []

def dedupe(items):
    seen = set()
    out = []
    for it in items:
        key = (it["title"] or "")[:80].lower()
        if key in seen: continue
        seen.add(key)
        out.append(it)
    return out

def main():
    secrets = load_secrets()
    api_key = secrets.get("newsapi_key", "")
    if not api_key or "PASTE" in api_key:
        print("NewsAPI key missing in config/secrets.json")
        sys.exit(1)

    all_items = []
    print(f"[news] fetching {len(SECTOR_QUERIES)} sectors...")
    for sector, q in SECTOR_QUERIES.items():
        items = fetch_sector(api_key, sector, q, page_size=8)
        print(f"  {sector:14s} → {len(items)} headlines")
        all_items.extend(items)

    # Dedupe + sort by recency (newest first), cap at 30
    all_items = dedupe(all_items)
    all_items.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    all_items = all_items[:30]

    payload = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "sectors":      list(SECTOR_QUERIES.keys()),
        "items":        all_items,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"[news] wrote {len(all_items)} headlines → {OUT_PATH}")

if __name__ == "__main__":
    main()
