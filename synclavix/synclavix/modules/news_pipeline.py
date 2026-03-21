import requests, json, os, re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

KEYWORDS = [
    "bitcoin","btc","ethereum","crypto","gold","xauusd",
    "s&p 500","sp500","nasdaq","dow jones","stock market",
    "fed","federal reserve","interest rate","inflation","cpi",
    "gdp","recession","unemployment","fomc","war","sanctions",
    "trade war","tariff","crash","rally","selloff","surge",
    "bank","crisis","default","bankruptcy","oil","commodity"
]

TIMEFRAMES = {
    "1h":  {"hours": 1,  "label": "BREAKING", "weight": 1.0},
    "6h":  {"hours": 6,  "label": "PENTING",  "weight": 0.7},
    "24h": {"hours": 24, "label": "KONTEKS",  "weight": 0.4},
}

# Multiple RSS feeds untuk verifikasi silang
RSS_FEEDS = [
    {"url": "https://news.google.com/rss/search?q=bitcoin+crypto&hl=en-US&gl=US&ceid=US:en", "source": "google_crypto"},
    {"url": "https://news.google.com/rss/search?q=gold+price+market&hl=en-US&gl=US&ceid=US:en", "source": "google_gold"},
    {"url": "https://news.google.com/rss/search?q=federal+reserve+interest+rate&hl=en-US&gl=US&ceid=US:en", "source": "google_fed"},
    {"url": "https://news.google.com/rss/search?q=stock+market+crash+rally&hl=en-US&gl=US&ceid=US:en", "source": "google_stocks"},
    {"url": "https://news.google.com/rss/search?q=inflation+recession+economy&hl=en-US&gl=US&ceid=US:en", "source": "google_macro"},
    {"url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD&region=US&lang=en-US", "source": "yahoo_btc"},
    {"url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F&region=US&lang=en-US", "source": "yahoo_gold"},
    {"url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US", "source": "yahoo_spx"},
    {"url": "https://www.investing.com/rss/news.rss", "source": "investing_com"},
    {"url": "https://www.marketwatch.com/rss/topstories", "source": "marketwatch"},
]

def similarity(a, b):
    a = re.sub(r'[^\w\s]', '', a.lower())
    b = re.sub(r'[^\w\s]', '', b.lower())
    return SequenceMatcher(None, a, b).ratio()

def is_relevant(text):
    return any(kw in text.lower() for kw in KEYWORDS)

def get_newsapi_topheadlines():
    """NewsAPI top-headlines (free tier compatible)"""
    if not NEWS_API_KEY:
        return []
    try:
        results = []
        # Business headlines
        for category in ["business", "general"]:
            r = requests.get("https://newsapi.org/v2/top-headlines", params={
                "category": category,
                "language": "en",
                "pageSize": 20,
                "apiKey": NEWS_API_KEY
            }, timeout=10)
            for a in r.json().get("articles", []):
                title = a.get("title", "")
                if title and is_relevant(title):
                    results.append({
                        "title": title,
                        "source": "newsapi_"+category,
                        "publisher": a.get("source", {}).get("name", ""),
                        "time": a.get("publishedAt", "")
                    })
        return results
    except Exception as e:
        print(f"  NewsAPI error: {e}")
        return []

def get_rss_feed(feed_info, hours):
    """Ambil satu RSS feed"""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        r = requests.get(feed_info["url"], timeout=10,
                        headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.content)
        results = []
        for item in root.findall(".//item")[:15]:
            title = item.findtext("title", "")
            pub_date = item.findtext("pubDate", "")
            try:
                pub_dt = parsedate_to_datetime(pub_date)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                if pub_dt < cutoff:
                    continue
            except:
                pass  # Kalau tidak bisa parse, tetap ambil
            if title and is_relevant(title):
                results.append({
                    "title": title,
                    "source": feed_info["source"],
                    "publisher": feed_info["source"],
                    "time": pub_date
                })
        return results
    except:
        return []

def get_all_rss(hours):
    """Ambil semua RSS feeds"""
    results = []
    for feed in RSS_FEEDS:
        items = get_rss_feed(feed, hours)
        results.extend(items)
    return results

def verify_news(headlines):
    """Cross-check: berita sama di 2+ sumber = VERIFIED"""
    verified = []
    used = set()
    for i, h1 in enumerate(headlines):
        if i in used:
            continue
        matching_sources = {h1["source"]}
        for j, h2 in enumerate(headlines):
            if i == j or j in used:
                continue
            # Sumber berbeda dan cukup mirip
            src1 = h1["source"].split("_")[0]
            src2 = h2["source"].split("_")[0]
            if src1 != src2 and similarity(h1["title"], h2["title"]) > 0.35:
                matching_sources.add(h2["source"])
                used.add(j)
        used.add(i)
        verified.append({
            "title": h1["title"],
            "sources": list(matching_sources),
            "source_count": len(matching_sources),
            "publisher": h1["publisher"],
            "time": h1["time"],
            "verified": len(matching_sources) >= 2
        })
    verified.sort(key=lambda x: (x["verified"], x["source_count"]), reverse=True)
    return verified

def get_multi_timeframe_news():
    print("\n[NEWS] Multi-timeframe scan...")
    all_results = {}

    # NewsAPI ambil sekali (tidak ada filter waktu di free tier)
    print("  Ambil NewsAPI top-headlines...")
    newsapi_headlines = get_newsapi_topheadlines()
    print(f"  NewsAPI: {len(newsapi_headlines)} berita relevan")

    for tf, cfg in TIMEFRAMES.items():
        hours = cfg["hours"]
        label = cfg["label"]
        print(f"\n  [{label} - {tf}]")

        # RSS dengan filter waktu
        rss_headlines = get_all_rss(hours)
        print(f"  RSS feeds: {len(rss_headlines)} berita")

        # Gabung semua sumber
        all_headlines = newsapi_headlines + rss_headlines

        # Verifikasi
        verified = verify_news(all_headlines)
        verified_only = [n for n in verified if n["verified"]]
        unverified = [n for n in verified if not n["verified"]]
        print(f"  Verified: {len(verified_only)} | Unverified: {len(unverified)}")

        top = verified_only[:5] + unverified[:3]
        all_results[tf] = {
            "label": label,
            "weight": cfg["weight"],
            "verified_count": len(verified_only),
            "news": top
        }

    # Format untuk LLM
    summary_text = "=== BERITA PASAR ===\n"
    for tf, data in all_results.items():
        news = data["news"]
        if not news:
            continue
        summary_text += f"\n[{data['label']} - {tf}]\n"
        for n in news[:4]:
            status = "?VERIFIED" if n["verified"] else "??"
            src = "+".join(set(s.split("_")[0] for s in n["sources"]))
            summary_text += f"{status}[{src}] {n['title'][:75]}\n"

    # Simpan cache
    os.makedirs("logs", exist_ok=True)
    with open("logs/news_cache.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": all_results
        }, f, indent=2, default=str)

    return all_results, summary_text

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("=== NEWS MULTI-TIMEFRAME TEST ===")
    results, text = get_multi_timeframe_news()
    print("\n" + text)
    total = sum(len(v["news"]) for v in results.values())
    total_verified = sum(v["verified_count"] for v in results.values())
    print(f"\nTotal: {total} berita | Verified: {total_verified}")
