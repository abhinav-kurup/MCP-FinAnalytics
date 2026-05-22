# MCP Financial Analyst Agent

A multi-service financial analysis agent built around the Model Context Protocol
(MCP). It accepts plain-English stock questions, gathers live market data through
dedicated MCP tools, and returns a structured markdown report with transparent
tool calls, reasoning notes, and optional charts.

This project is designed as a portfolio-friendly demonstration of agentic tool
orchestration: the LLM reasons about what it needs, MCP servers fetch the data,
and the final answer is synthesized only from verified tool results.

## What It Does

- Compares stocks over a requested time window.
- Fetches current and historical price data with `yfinance`.
- Calculates technical indicators such as RSI, MACD, Bollinger Bands, and moving averages.
- Pulls company fundamentals such as P/E, EPS, margins, revenue growth, and analyst metadata.
- Scores recent news headlines with VADER sentiment.
- Generates base64 PNG charts for price, RSI, and comparison views.
- Returns a JSON response that includes the final markdown report plus the actual MCP tool calls made.

## Architecture

```text
User / Client
    |
    v
FastAPI Agent API (:8000)
    |
    v
LangGraph Orchestrator
    |
    | MCP over SSE
    v
+----------------------+----------------------+----------------------+
| stock-data (:8001)   | technical (:8002)    | news (:8003)         |
| prices, history      | RSI, MACD, MAs       | headlines, sentiment |
+----------------------+----------------------+----------------------+
| fundamentals (:8004) | reports (:8005)      |
| valuation metrics    | chart generation     |
+----------------------+----------------------+
```

Each capability runs as its own MCP server. The agent discovers available tools,
asks the model which tools to call, executes them, and then produces the final
report from the collected results.

## Project Layout

```text
.
|-- agent/
|   |-- main.py              # FastAPI entry point and /analyze route
|   |-- orchestrator.py      # LangGraph reasoning/tool loop
|   |-- mcp_client.py        # MCP client session manager
|   `-- prompts.py           # System and report prompts
|-- servers/
|   |-- stock_data/          # Price and historical data tools
|   |-- technical_analysis/  # RSI, MACD, Bollinger, moving averages
|   |-- news_sentiment/      # News headlines and VADER sentiment
|   |-- fundamentals/        # Company fundamentals
|   `-- report_generator/    # Base64 chart generation
|-- docker-compose.yml
|-- requirements.txt
|-- .env.example
`-- README.md
```

## API

### `POST /analyze`

Request:

```json
{
  "query": "Compare NVDA and AMD over the last month. Which one looks more interesting right now based on their RSI and MACD?",
  "options": {
    "include_charts": true,
    "report_format": "markdown"
  }
}
```

Response shape:

```json
{
  "query": "...",
  "report": "## NVDA and AMD - Financial Analysis Report\n...",
  "tool_calls_made": [
    {
      "tool": "compare_stocks",
      "args": {
        "tickers": ["NVDA", "AMD"],
        "period": "1mo"
      }
    }
  ],
  "reasoning_steps": [],
  "duration_seconds": 3.54,
  "charts": {
    "generate_comparison_chart_NVDA_AMD": "base64_png_here"
  }
}
```

The `tool_calls_made` field is intentionally exposed. It proves which MCP tools
were actually used and helps debug whether the report was built from real data.

## Quick Start

### 1. Create your environment file

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set at least one LLM provider key. The default provider is Groq:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
```

`NEWS_API_KEY` is optional. If it is not set, the news server falls back to
Yahoo Finance news through `yfinance`.

### 2. Start the stack

```powershell
docker compose up --build
```

The API will be available at:

```text
http://localhost:8000
```

Interactive FastAPI docs:

```text
http://localhost:8000/docs
```

### 3. Send a request

```powershell
$body = @{
  query = "Compare NVDA and AMD over the last month. Which one looks more interesting right now based on their RSI and MACD?"
  options = @{
    include_charts = $true
    report_format = "markdown"
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/analyze" `
  -ContentType "application/json" `
  -Body $body
```

Or with curl:

```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare NVDA and AMD over the last month. Which one looks more interesting right now based on their RSI and MACD?",
    "options": {
      "include_charts": true,
      "report_format": "markdown"
    }
  }'
```
<!-- 
## MCP Tools

### Stock Data

- `get_stock_price(ticker)`
- `get_historical_prices(ticker, period, interval)`
- `compare_stocks(tickers, period)`

### Technical Analysis

- `get_rsi(ticker, period, window)`
- `get_macd(ticker, period)`
- `get_bollinger_bands(ticker, period, window)`
- `get_moving_averages(ticker, periods)`

### News Sentiment

- `get_news_sentiment(ticker, company_name, days)`

### Fundamentals

- `get_fundamentals(ticker)`

### Report Generator

- `generate_price_chart(ticker, period, include_volume)`
- `generate_comparison_chart(tickers, period)`
- `generate_rsi_chart(ticker, period)`

## Design Principles

### The LLM reasons, tools fetch

The model should not invent prices, indicators, earnings dates, or headline
sentiment. Financial numbers must come from MCP tool results.

### MCP servers are isolated

Each server owns one category of capability. That makes the system easier to
debug, explain, and extend.

### Reports are transparent

The response includes `tool_calls_made`, `reasoning_steps`, and `charts` so the
caller can inspect what happened instead of treating the answer as a black box.

## Local Development

You can run services outside Docker by setting:

```env
LOCAL_DEV=true
```

Then run each server from its folder:

```powershell
python server.py
```

And run the agent:

```powershell
cd agent
python main.py
```

When `LOCAL_DEV=true`, the agent connects to `localhost` instead of Docker
service hostnames.

## Troubleshooting

### `mcp run` does not support `--port`

This project runs MCP servers with:

```dockerfile
CMD ["python", "server.py"]
```

The server script configures its own port through the `PORT` environment
variable. If you see `No such option '--port'`, rebuild the images:

```powershell
docker compose up --build
```

### `FastMCP.run() got an unexpected keyword argument 'host'`

For the SDK version used here, `host` and `port` are configured on the
`FastMCP(...)` constructor, not passed into `mcp.run(...)`.

### The report says analysis is unavailable

That usually means the agent could not discover any MCP tools. Check that the
five MCP containers are running and that the agent logs show successful
connections to:

- `stock-data:8001`
- `technical-analysis:8002`
- `news-sentiment:8003`
- `fundamentals:8004`
- `report-generator:8005`

### Charts are missing

Make sure your request includes:

```json
{
  "options": {
    "include_charts": true
  }
}
```

The model still decides which chart tools are relevant, but this option tells
the planner that charts are expected.

## Example Questions

- `Compare NVDA and AMD over the last month using RSI and MACD.`
- `Analyze TSLA technically and include a price chart.`
- `What do fundamentals and sentiment say about MSFT right now?`
- `Compare AAPL, MSFT, and GOOGL over three months.`

## Disclaimer

This project is for educational and demonstration purposes only. It is not a
trading bot, investment adviser, or financial recommendation system. Market data
may be delayed or incomplete depending on upstream providers. -->
