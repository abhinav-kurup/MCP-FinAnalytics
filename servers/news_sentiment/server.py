from mcp.server.fastmcp import FastMCP
import yfinance as yf
import os
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import List, Dict, Any

mcp = FastMCP("news_sentiment")
analyzer = SentimentIntensityAnalyzer()

def _get_yfinance_news(ticker: str) -> list[dict]:
    """Fallback to yfinance news"""
    t = yf.Ticker(ticker)
    news = t.news
    headlines = []
    for item in news[:10]:
        title = item.get('title', '')
        headlines.append({
            "title": title,
            "source": item.get('publisher', 'Yahoo Finance'),
            "date": item.get('providerPublishTime', ''),
        })
    return headlines

@mcp.tool()
def get_news_sentiment(ticker: str, company_name: str, days: int = 7) -> dict:
    """
    Returns overall_sentiment, sentiment_label, article_count, headlines, summary
    """
    try:
        api_key = os.getenv("NEWS_API_KEY")
        headlines = []
        
        if api_key and api_key != "your_key_here":
            # Use NewsAPI
            url = f"https://newsapi.org/v2/everything?q={ticker} OR \"{company_name}\"&language=en&sortBy=publishedAt&pageSize=10&apiKey={api_key}"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                for article in data.get("articles", []):
                    headlines.append({
                        "title": article.get("title", ""),
                        "source": article.get("source", {}).get("name", "Unknown"),
                        "date": article.get("publishedAt", ""),
                    })
            else:
                # Fallback to yfinance if NewsAPI fails
                headlines = _get_yfinance_news(ticker)
        else:
            # Fallback to yfinance if no API key
            headlines = _get_yfinance_news(ticker)
            
        if not headlines:
            return {"error": f"No news found for {ticker}"}
            
        scored_headlines = []
        total_score = 0.0
        
        for h in headlines:
            title = h["title"]
            if not title:
                continue
            score = analyzer.polarity_scores(title)['compound']
            h["sentiment_score"] = score
            scored_headlines.append(h)
            total_score += score
            
        article_count = len(scored_headlines)
        if article_count == 0:
            return {"error": "No scorable headlines found."}
            
        overall_sentiment = total_score / article_count
        
        sentiment_label = "neutral"
        if overall_sentiment <= -0.5:
            sentiment_label = "very_negative"
        elif -0.5 < overall_sentiment <= -0.1:
            sentiment_label = "negative"
        elif 0.1 <= overall_sentiment < 0.5:
            sentiment_label = "positive"
        elif overall_sentiment >= 0.5:
            sentiment_label = "very_positive"
            
        summary_texts = [h["title"] for h in scored_headlines[:3]]
        summary = " | ".join(summary_texts)
        
        return {
            "overall_sentiment": float(overall_sentiment),
            "sentiment_label": sentiment_label,
            "article_count": article_count,
            "headlines": scored_headlines,
            "summary": summary
        }
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    mcp.run(transport="sse")
