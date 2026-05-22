from mcp.server.fastmcp import FastMCP
import yfinance as yf

mcp = FastMCP("fundamentals")

@mcp.tool()
def get_fundamentals(ticker: str) -> dict:
    """
    Returns company fundamental financial data for a given ticker.
    Fields include P/E, EPS, revenue growth, profit margin, analyst recommendations.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info
        
        if not info or len(info) <= 1:
            return {"error": f"No fundamental data found for ticker {ticker}"}
            
        def safe_get(key):
            return info.get(key, None)
            
        # Recommendation format from yfinance might vary, often stored in 'recommendationKey'
        analyst_rec = safe_get('recommendationKey')
        if analyst_rec:
            analyst_rec = analyst_rec.lower()
        else:
            analyst_rec = "unknown"
            
        return {
            "company_name": safe_get('shortName') or safe_get('longName'),
            "sector": safe_get('sector'),
            "pe_ratio": safe_get('trailingPE'),
            "forward_pe": safe_get('forwardPE'),
            "eps": safe_get('trailingEps'),
            "revenue_growth": safe_get('revenueGrowth'),
            "profit_margin": safe_get('profitMargins'),
            "debt_to_equity": safe_get('debtToEquity'),
            "next_earnings_date": safe_get('earningsDate'), # Note: might be a list of dates
            "analyst_recommendation": analyst_rec,
            "price_target": safe_get('targetMeanPrice')
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    mcp.run(transport="sse")
