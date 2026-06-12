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

# Alias so push_to_api can use it without a separate import block
_requests = requests

ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / "config" / "secrets.json"
OUT_PATH = ROOT / "public_html" / "data" / "news.json"

# Sector → NewsAPI search query
SECTOR_QUERIES = {
    "AI & Quantum": '("artificial intelligence" OR "quantum computing" OR "AI chip" OR "qubit" OR Nvidia OR Anthropic OR OpenAI OR IonQ OR Quantinuum OR Rigetti OR Palantir OR "C3.ai" OR Arista OR "Super Micro" OR AMD OR "Applied Digital") AND (stock OR shares OR earnings OR revenue OR CEO OR "market cap" OR investor OR trading OR "Wall Street")',
    "Biotech":      '(biotech OR mRNA OR CRISPR OR "gene therapy" OR "FDA approval" OR clinical OR Moderna OR BioNTech OR Vertex OR Regeneron OR Illumina) AND (stock OR earnings OR FDA OR trial OR shares)',
    "Energy":       '(oil OR LNG OR renewables OR solar OR "energy storage" OR Aramco OR Exxon OR Chevron OR "First Solar" OR "NextEra") AND (stock OR earnings OR price OR production OR investor)',
    "Defense":      '(defense OR Lockheed OR Raytheon OR "Northrop Grumman" OR BAE OR hypersonic OR "missile defense" OR "General Dynamics" OR "L3Harris") AND (stock OR contract OR earnings OR Pentagon)',
    "Finance":      '(JPMorgan OR Goldman OR "Bank of America" OR Visa OR Mastercard OR "Federal Reserve" OR "interest rate" OR earnings OR "S&P 500") AND (stock OR market OR earnings OR investor)',
}

# Domains to exclude — NewsAPI free tier ignores excludeDomains param,
# so we filter post-fetch by URL and source name.
EXCLUDE_DOMAINS_LIST = [
    "pypi.org", "github.com", "stackoverflow.com", "reddit.com",
    "medium.com", "dev.to", "hackernews.com", "npmjs.com",
    "ycombinator.com", "news.ycombinator.com", "lobste.rs",
]

def _is_excluded(article: dict) -> bool:
    """Return True if this article should be filtered out."""
    url = (article.get("url") or "").lower()
    source = (article.get("source") or {}).get("name", "").lower()
    for domain in EXCLUDE_DOMAINS_LIST:
        if domain in url or domain.split(".")[0] in source:
            return True
    return False

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
            articles = [a for a in data.get("articles", []) if a.get("title") and not _is_excluded(a)]
            return [{
                "title":        a.get("title", "").split(" - ")[0],
                "source":       (a.get("source") or {}).get("name", ""),
                "sector":       sector,
                "published_at": a.get("publishedAt"),
                "url":          a.get("url", "#"),
            } for a in articles]
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

    # ── Push to Supabase via Cloud Run API (dual-write; HostGator file already written) ──
    push_to_api(secrets, "news", payload)


def push_to_api(secrets, data_type, payload):
    """
    Push a tracker JSON payload to Cloud Run so it lands in Supabase.
    Silent on failure — HostGator file write already succeeded.
    """
    api_url = secrets.get("api_url", "")
    api_key  = secrets.get("internal_api_key", "")
    platform = secrets.get("platform", "lvl13")

    if not api_url or not api_key:
        print(f"  [push] api_url/internal_api_key not in secrets.json — skipping push for {data_type}")
        return

    endpoint = f"{api_url.rstrip('/')}/internal/tracker/push"
    try:
        r = _requests.post(
            endpoint,
            json={"data_type": data_type, "platform": platform, "data": payload},
            headers={"X-Internal-Key": api_key},
            timeout=15,
        )
        if r.status_code == 200:
            print(f"  [push] ✓ {data_type} → Supabase (pushed_at={r.json().get('pushed_at','')})")
        else:
            print(f"  [push] ✗ {data_type} HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  [push] ✗ {data_type} error: {e}")


if __name__ == "__main__":
    main()
