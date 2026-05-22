import os
import asyncio
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from mcp_client import mcp_manager
from orchestrator import agent_graph

app = FastAPI(title="MCP Financial Analyst API")

class AnalyzeRequest(BaseModel):
    query: str
    options: Optional[Dict[str, Any]] = None

class AnalyzeResponse(BaseModel):
    query: str
    report: str
    tool_calls_made: List[Dict[str, Any]]
    reasoning_steps: List[str]
    duration_seconds: float
    charts: Dict[str, str]

@app.on_event("startup")
async def startup_event():
    # Attempt to connect to the MCP servers defined in environment variables
    # For a docker compose setup, the hostnames are the service names
    # E.g., stock-data:8001
    
    # Let's give the servers a moment to start up in docker-compose
    await asyncio.sleep(2)
    
    servers = {
        "stock_data": f"http://stock-data:{os.getenv('STOCK_DATA_PORT', '8001')}",
        "technical_analysis": f"http://technical-analysis:{os.getenv('TECHNICAL_ANALYSIS_PORT', '8002')}",
        "news_sentiment": f"http://news-sentiment:{os.getenv('NEWS_SENTIMENT_PORT', '8003')}",
        "fundamentals": f"http://fundamentals:{os.getenv('FUNDAMENTALS_PORT', '8004')}",
        "report_generator": f"http://report-generator:{os.getenv('REPORT_GENERATOR_PORT', '8005')}",
    }
    
    # We could also support running on localhost for direct dev
    if os.getenv("LOCAL_DEV") == "true":
        servers = {k: v.replace(k.replace("_", "-"), "localhost") for k, v in servers.items()}
    
    for name, url in servers.items():
        await mcp_manager.connect_to_server(name, url)
        
@app.on_event("shutdown")
async def shutdown_event():
    await mcp_manager.close()

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    start_time = time.time()
    
    try:
        # Run the LangGraph agent
        initial_state = {
            "query": request.query,
            "tickers": [], # Optionally extract tickers earlier if needed
            "tool_calls": [],
            "tool_results": [],
            "reasoning_steps": [],
            "messages": []
        }
        
        # Invoke graph
        final_state = await agent_graph.ainvoke(initial_state)
        
        # Extract charts if any base64 charts were returned in tool_results
        charts = {}
        for res in final_state.get("tool_results", []):
            if "result" in res and isinstance(res["result"], dict):
                r = res["result"]
                if "chart_base64" in r:
                    charts[res["tool"]] = r["chart_base64"]
                # some tools might return it as string if parsing failed, handle appropriately

        duration = time.time() - start_time
        
        return AnalyzeResponse(
            query=request.query,
            report=final_state.get("final_report", ""),
            tool_calls_made=final_state.get("tool_calls", []),
            reasoning_steps=final_state.get("reasoning_steps", []),
            duration_seconds=round(duration, 2),
            charts=charts
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("AGENT_API_PORT", "8000")))
