from mcp.server.fastmcp import FastMCP
import os
import yfinance as yf
import pandas_ta as ta
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import mplfinance as mpf
import base64
from io import BytesIO
import pandas as pd

mcp = FastMCP(
    "report_generator",
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "8005")),
)

# Set a cleaner style globally for matplotlib
plt.style.use('seaborn-v0_8-darkgrid')

def _fig_to_base64(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig) # Prevent memory leaks
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

@mcp.tool()
def generate_price_chart(ticker: str, period: str = "3mo", include_volume: bool = True) -> dict:
    """
    Generates a candlestick price chart. Returns {chart_base64: str, format: "png"}
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist.empty:
            return {"error": f"No data found for {ticker}"}
            
        # mplfinance needs a pandas dataframe with Open, High, Low, Close, Volume
        fig, axlist = mpf.plot(
            hist,
            type='candle',
            volume=include_volume,
            title=f"{ticker} Price ({period})",
            style='charles',
            returnfig=True,
            figsize=(10, 6)
        )
        
        b64 = _fig_to_base64(fig)
        return {"chart_base64": b64, "format": "png"}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def generate_comparison_chart(tickers: list[str], period: str = "3mo") -> dict:
    """
    Generates a comparison line chart for multiple tickers, normalised to 100.
    """
    try:
        data = yf.download(tickers, period=period, group_by='ticker', auto_adjust=True)
        if data.empty:
            return {"error": "No data found"}
            
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if len(tickers) == 1:
            ticker = tickers[0]
            series = data['Close'].dropna()
            normalized = (series / series.iloc[0]) * 100
            ax.plot(normalized.index, normalized, label=ticker)
        else:
            for ticker in tickers:
                if ticker in data and 'Close' in data[ticker]:
                    series = data[ticker]['Close'].dropna()
                    if not series.empty:
                        normalized = (series / series.iloc[0]) * 100
                        ax.plot(normalized.index, normalized, label=ticker)
                        
        ax.set_title(f"Comparison ({period}) - Normalized to 100")
        ax.set_ylabel("Relative Performance")
        ax.legend()
        
        b64 = _fig_to_base64(fig)
        return {"chart_base64": b64, "format": "png"}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def generate_rsi_chart(ticker: str, period: str = "6mo") -> dict:
    """
    Generates an RSI chart with overbought/oversold reference lines.
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist.empty or len(hist) < 15:
            return {"error": "Not enough data"}
            
        rsi_series = hist.ta.rsi(length=14)
        if rsi_series is None or rsi_series.empty:
            return {"error": "Could not calculate RSI"}
            
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(rsi_series.index, rsi_series, label='RSI (14)', color='purple')
        ax.axhline(70, color='red', linestyle='--', alpha=0.5, label='Overbought (70)')
        ax.axhline(30, color='green', linestyle='--', alpha=0.5, label='Oversold (30)')
        ax.set_ylim(0, 100)
        ax.set_title(f"{ticker} RSI ({period})")
        ax.legend()
        
        b64 = _fig_to_base64(fig)
        return {"chart_base64": b64, "format": "png"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    mcp.run(transport="sse")
