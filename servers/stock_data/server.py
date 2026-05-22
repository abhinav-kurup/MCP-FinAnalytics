from mcp.server.fastmcp import FastMCP
import yfinance as yf
from typing import List, Dict, Any

mcp = FastMCP("stock_data")

@mcp.tool()
def get_stock_price(ticker: str) -> dict:
    """Returns current price, change, change_pct, volume, market_cap for a ticker."""
    try:
        t = yf.Ticker(ticker)
        # Using fast_info as it is faster and more reliable for basic stats
        info = t.fast_info
        
        # fallback to history if some data is not in fast_info
        hist = t.history(period="5d")
        if hist.empty:
            return {"error": f"No data found for ticker {ticker}"}
            
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
        volume = hist['Volume'].iloc[-1]
        
        try:
            market_cap = info.market_cap
        except AttributeError:
            market_cap = None
            
        return {
            "current_price": float(current_price),
            "change": float(change),
            "change_pct": float(change_pct),
            "volume": int(volume),
            "market_cap": market_cap
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_historical_prices(ticker: str, period: str = "1mo", interval: str = "1d") -> list[dict]:
    """
    Returns historical price data for a ticker.
    period: "1mo", "3mo", "6mo", "1y", etc.
    interval: "1d", "1h", etc.
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period, interval=interval)
        if hist.empty:
            return []
            
        result = []
        for index, row in hist.iterrows():
            result.append({
                "date": str(index),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": int(row['Volume'])
            })
        return result
    except Exception as e:
        return [{"error": str(e)}]

@mcp.tool()
def compare_stocks(tickers: list[str], period: str = "1mo") -> dict:
    """
    Returns side-by-side returns, and relative performance for multiple tickers.
    """
    try:
        data = yf.download(tickers, period=period, group_by='ticker', auto_adjust=True)
        if data.empty:
            return {"error": "No data found for the given tickers"}
            
        result = {}
        # If there's only one ticker, yf.download returns a single level column
        if len(tickers) == 1:
            ticker = tickers[0]
            if data['Close'].empty:
                return {"error": f"No data for {ticker}"}
            start_price = data['Close'].iloc[0]
            end_price = data['Close'].iloc[-1]
            ret = (end_price - start_price) / start_price * 100
            result[ticker] = {
                "start_price": float(start_price),
                "end_price": float(end_price),
                "return_pct": float(ret)
            }
            return result
            
        for ticker in tickers:
            try:
                # Need to handle missing data for some tickers
                ticker_data = data[ticker]['Close'].dropna()
                if ticker_data.empty:
                    continue
                start_price = ticker_data.iloc[0]
                end_price = ticker_data.iloc[-1]
                ret = (end_price - start_price) / start_price * 100
                result[ticker] = {
                    "start_price": float(start_price),
                    "end_price": float(end_price),
                    "return_pct": float(ret)
                }
            except Exception as e:
                result[ticker] = {"error": str(e)}
                
        return result
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    # When running as script, use the built-in MCP server
    # FastMCP uses standard ASGI app if run with CLI, but we can also use built in run
    mcp.run(transport="sse")
