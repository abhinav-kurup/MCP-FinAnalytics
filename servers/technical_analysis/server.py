from mcp.server.fastmcp import FastMCP
import yfinance as yf
import pandas_ta as ta
from typing import List, Dict, Any

mcp = FastMCP("technical_analysis")

def _get_history(ticker: str, period: str) -> yf.Ticker:
    """Helper to fetch history data"""
    t = yf.Ticker(ticker)
    hist = t.history(period=period)
    return hist

@mcp.tool()
def get_rsi(ticker: str, period: str = "6mo", window: int = 14) -> dict:
    """
    Returns current_rsi, signal ("oversold" | "neutral" | "overbought"), history.
    Requires at least window+1 periods of data. Using 6mo by default.
    """
    try:
        hist = _get_history(ticker, period)
        if hist.empty or len(hist) <= window:
            return {"error": f"Not enough data for {ticker} to calculate RSI with window {window}"}
            
        rsi_series = hist.ta.rsi(length=window)
        if rsi_series is None or rsi_series.empty:
            return {"error": "Failed to calculate RSI"}
            
        current_rsi = float(rsi_series.iloc[-1])
        
        signal = "neutral"
        if current_rsi < 30:
            signal = "oversold"
        elif current_rsi > 70:
            signal = "overbought"
            
        # Optional: return a short history of RSI
        rsi_history = [float(x) for x in rsi_series.tail(10).dropna()]
        
        return {
            "current_rsi": current_rsi,
            "signal": signal,
            "history": rsi_history
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_macd(ticker: str, period: str = "6mo") -> dict:
    """
    Returns macd_line, signal_line, histogram, crossover_signal ("bullish" | "bearish" | "none").
    """
    try:
        hist = _get_history(ticker, period)
        if hist.empty or len(hist) < 35:
            return {"error": "Not enough data for MACD"}
            
        macd_df = hist.ta.macd()
        if macd_df is None or macd_df.empty:
            return {"error": "Failed to calculate MACD"}
            
        # pandas_ta macd returns columns like MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
        macd_col = [c for c in macd_df.columns if c.startswith("MACD_")][0]
        hist_col = [c for c in macd_df.columns if c.startswith("MACDh_")][0]
        signal_col = [c for c in macd_df.columns if c.startswith("MACDs_")][0]
        
        current_macd = float(macd_df[macd_col].iloc[-1])
        current_signal = float(macd_df[signal_col].iloc[-1])
        current_hist = float(macd_df[hist_col].iloc[-1])
        
        prev_macd = float(macd_df[macd_col].iloc[-2])
        prev_signal = float(macd_df[signal_col].iloc[-2])
        
        crossover_signal = "none"
        if prev_macd < prev_signal and current_macd > current_signal:
            crossover_signal = "bullish"
        elif prev_macd > prev_signal and current_macd < current_signal:
            crossover_signal = "bearish"
            
        return {
            "macd_line": current_macd,
            "signal_line": current_signal,
            "histogram": current_hist,
            "crossover_signal": crossover_signal
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_bollinger_bands(ticker: str, period: str = "6mo", window: int = 20) -> dict:
    """
    Returns upper, middle, lower, current_price, position ("above_upper" | "inside" | "below_lower")
    """
    try:
        hist = _get_history(ticker, period)
        if hist.empty or len(hist) <= window:
            return {"error": "Not enough data for Bollinger Bands"}
            
        bbands_df = hist.ta.bbands(length=window)
        if bbands_df is None or bbands_df.empty:
            return {"error": "Failed to calculate Bollinger Bands"}
            
        lower_col = [c for c in bbands_df.columns if c.startswith("BBL_")][0]
        middle_col = [c for c in bbands_df.columns if c.startswith("BBM_")][0]
        upper_col = [c for c in bbands_df.columns if c.startswith("BBU_")][0]
        
        current_price = float(hist['Close'].iloc[-1])
        upper = float(bbands_df[upper_col].iloc[-1])
        middle = float(bbands_df[middle_col].iloc[-1])
        lower = float(bbands_df[lower_col].iloc[-1])
        
        position = "inside"
        if current_price > upper:
            position = "above_upper"
        elif current_price < lower:
            position = "below_lower"
            
        return {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "current_price": current_price,
            "position": position
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_moving_averages(ticker: str, periods: list[int] = [20, 50, 200]) -> dict:
    """
    Returns {20: float, 50: float, 200: float}, trend ("uptrend" | "downtrend" | "mixed")
    Requires a longer period for 200-day MA.
    """
    try:
        max_period = max(periods)
        # Fetch 1y to be safe for 200 DMA
        hist = _get_history(ticker, "1y")
        if hist.empty or len(hist) <= max_period:
            return {"error": f"Not enough data for moving averages up to {max_period} days"}
            
        result = {}
        for p in periods:
            sma_series = hist.ta.sma(length=p)
            if sma_series is not None and not sma_series.empty:
                result[str(p)] = float(sma_series.iloc[-1])
                
        # Calculate trend
        trend = "mixed"
        if "20" in result and "50" in result and "200" in result:
            if result["20"] > result["50"] > result["200"]:
                trend = "uptrend"
            elif result["20"] < result["50"] < result["200"]:
                trend = "downtrend"
                
        return {
            "averages": result,
            "trend": trend
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    mcp.run(transport="sse")
