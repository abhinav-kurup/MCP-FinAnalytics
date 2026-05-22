FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV PORT=8004

CMD ["mcp", "run", "server.py", "--transport", "sse", "--port", "8004"]
