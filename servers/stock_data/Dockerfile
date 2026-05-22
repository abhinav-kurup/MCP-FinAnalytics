FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# Assuming MCP SSE server runs on port 8001 inside
ENV PORT=8001

# Command using mcp CLI to start the FastMCP SSE server
# Or we can run python server.py if we implement the uvicorn hook
CMD ["mcp", "run", "server.py", "--transport", "sse", "--port", "8001"]
