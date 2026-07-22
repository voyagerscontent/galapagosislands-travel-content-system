# Pattern Breaker service container.
# Build:  docker build -t pattern-breaker .
# Run:    docker run -p 8080:8080 -e ANTHROPIC_API_KEY=sk-ant-... pattern-breaker
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
ENV PORT=8080

# curl is used as the Claude transport when behind an intercepting proxy.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

CMD ["uvicorn", "service.api:app", "--host", "0.0.0.0", "--port", "8080"]
