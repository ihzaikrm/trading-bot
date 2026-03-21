# core/news_sentiment.py
import os
import requests
from datetime import datetime, timedelta

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

def get_news_sentiment(asset_name, asset_type="crypto"):
    """
    Ambil berita terbaru dan analisis sentimen sederhana.
    Mengembalikan dict dengan sentimen dan skor.
    """
    if not NEWS_API_KEY:
        return {"sentiment": "NEUTRAL", "score": 0, "articles": 0}
    
    # Mapping nama aset ke query
    query_map = {
        "Bitcoin": "bitcoin",
        "Gold": "gold",
        "S&P 500": "S&P 500",
    }
    q = query_map.get(asset_name, asset_name.lower())
    
    # Ambil berita 7 hari terakhir
    from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": q,
        "from": from_date,
        "sortBy": "relevancy",
        "language": "en",
        "pageSize": 5,
        "apiKey": NEWS_API_KEY
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return {"sentiment": "NEUTRAL", "score": 0, "articles": 0}
        data = r.json()
        articles = data.get("articles", [])
        if not articles:
            return {"sentiment": "NEUTRAL", "score": 0, "articles": 0}
        
        # Analisis sentimen sederhana berdasarkan judul (rule-based)
        positive_words = ["surge", "rally", "gain", "bull", "up", "high", "record", "positive", "optimistic"]
        negative_words = ["drop", "fall", "crash", "bear", "down", "low", "negative", "fear", "plunge"]
        
        score = 0
        for article in articles:
            title = article.get("title", "").lower()
            desc = article.get("description", "").lower()
            text = title + " " + desc
            for w in positive_words:
                if w in text:
                    score += 1
                    break
            for w in negative_words:
                if w in text:
                    score -= 1
                    break
        
        if score > 1:
            sentiment = "BULLISH"
        elif score < -1:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"
        
        return {
            "sentiment": sentiment,
            "score": score,
            "articles": len(articles)
        }
    except Exception as e:
        print(f"[News] Error: {e}")
        return {"sentiment": "NEUTRAL", "score": 0, "articles": 0}

def get_fear_greed():
    """Ambil Fear & Greed Index dari alternative.me"""
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        if r.status_code != 200:
            return {"value": 50, "classification": "Neutral"}
        data = r.json()
        item = data["data"][0]
        return {
            "value": int(item["value"]),
            "classification": item["value_classification"]
        }
    except Exception as e:
        print(f"[FNG] Error: {e}")
        return {"value": 50, "classification": "Neutral"}