# ── content-pipeline FastAPI service ────────────────────────────────────────
# Runs the deterministic guardrail + lexical injection service on port 8080.
# Deploy on any VPS (DigitalOcean, Hetzner, etc.) alongside n8n.
#
# Build:   docker build -t content-pipeline .
# Run:     docker run -d --restart unless-stopped -p 8080:8080 content-pipeline
# Health:  curl http://localhost:8080/health
FROM python:3.11-slim

# System deps for nltk tokenizer data download
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python package (service extras = fastapi + uvicorn)
COPY content-pipeline/ ./content-pipeline/
RUN pip install --no-cache-dir -e "./content-pipeline[service]"

# Pre-download nltk data at build time so containers start instantly
RUN python - <<'PYEOF'
import nltk
for pkg in ["punkt", "punkt_tab", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng"]:
    nltk.download(pkg, quiet=True)
PYEOF

# Warm the lexicon import (validates JSON at build time — fails fast if broken)
RUN python -c "from content_pipeline.lexical_injector.injector import load_lexicon; load_lexicon(); print('lexicon OK')"

EXPOSE 8080

# Single worker is fine — all endpoints are CPU-bound pure Python.
# For high traffic, increase --workers (one per vCPU).
CMD ["uvicorn", "content_pipeline.service.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "2", \
     "--log-level", "info"]
