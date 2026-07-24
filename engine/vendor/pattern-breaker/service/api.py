"""
FastAPI service — the stable, repurposable interface for the pattern-breaker.

This is the "Option B" robust integration surface. n8n (or any other repo, app,
or cron job) just makes HTTP calls; it never needs the Python source or a shared
filesystem. Deploy once, call forever.

Endpoints
---------
GET  /health                 -> service + config status
GET  /config                 -> the active thresholds (read-only)
POST /detect      {text}     -> Phase 1 only. Deterministic flags. No LLM. Fast.
POST /restructure {text,flagged_spans?} -> Phase 2 only (needs Claude).
POST /process     {text}     -> Full 2-phase run + re-verification. The main one.

Run locally:
    pip install -r requirements.txt
    export PB_USE_PROXY=1            # if behind the credential proxy
    # or: export ANTHROPIC_API_KEY=sk-ant-...
    uvicorn service.api:app --host 0.0.0.0 --port 8080

Auth (optional but recommended for public deploys):
    export PB_API_TOKEN=some-long-secret
    then send header:  Authorization: Bearer some-long-secret
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from detector.detector import detect          # noqa: E402
from restructurer.restructure import restructure  # noqa: E402
from pipeline import process                   # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "thresholds.json"

app = FastAPI(
    title="Pattern Breaker",
    version="1.0.0",
    description="Two-phase deterministic AI-pattern detector + constrained "
                "Claude Sonnet restructurer.",
)


# --- request/response models --------------------------------------------------
class DetectRequest(BaseModel):
    text: str = Field(..., description="Raw text to analyze.")
    config_path: Optional[str] = None


class SpanIn(BaseModel):
    start: int
    end: int
    factors: List[str] = []
    reasons: List[str] = []


class RestructureRequest(BaseModel):
    text: str
    flagged_spans: Optional[List[SpanIn]] = None
    max_passes: int = 3
    temperature: float = 0.4


class ProcessRequest(BaseModel):
    text: str
    max_passes: int = 3
    temperature: float = 0.4
    config_path: Optional[str] = None


# --- auth helper --------------------------------------------------------------
def _check_auth(authorization: Optional[str]) -> None:
    token = os.environ.get("PB_API_TOKEN")
    if not token:
        return  # auth disabled
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token.")


# --- endpoints ----------------------------------------------------------------
@app.get("/health")
def health():
    live = bool(os.environ.get("ANTHROPIC_API_KEY")) or os.environ.get("PB_USE_PROXY") == "1"
    return {
        "ok": True,
        "service": "pattern-breaker",
        "version": "1.0.0",
        "phase2_live": live,
        "claude_model": os.environ.get("PB_CLAUDE_MODEL", "claude-sonnet-4-6"),
        "config_exists": CONFIG_PATH.exists(),
    }


@app.get("/config")
def get_config():
    return json.loads(CONFIG_PATH.read_text())


@app.post("/detect")
def detect_endpoint(req: DetectRequest, authorization: Optional[str] = Header(None)):
    _check_auth(authorization)
    rep = detect(req.text, config_path=req.config_path)
    return rep.to_dict()


@app.post("/restructure")
def restructure_endpoint(req: RestructureRequest, authorization: Optional[str] = Header(None)):
    _check_auth(authorization)
    if req.flagged_spans is None:
        rep = detect(req.text)
        spans = rep.flagged_spans
    else:
        spans = [s.dict() for s in req.flagged_spans]
    res = restructure(req.text, spans, max_passes=req.max_passes,
                      temperature=req.temperature)
    return res.to_dict()


@app.post("/process")
def process_endpoint(req: ProcessRequest, authorization: Optional[str] = Header(None)):
    _check_auth(authorization)
    return process(req.text, config_path=req.config_path,
                   max_passes=req.max_passes, temperature=req.temperature)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
