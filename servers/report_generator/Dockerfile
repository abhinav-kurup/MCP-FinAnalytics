FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for matplotlib (if needed for some fonts/formats)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV PORT=8005

CMD ["python", "server.py"]
