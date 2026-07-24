"""FastAPI service — exposes the DETERMINISTIC modules so the live n8n pipeline can
call them over HTTP (like the pattern-breaker workflow), with no LLM on this side.

The three endpoints below need no model and can be wired into the live humanize /
post-humanize stages immediately:
  POST /macro/evaluate  -> section-level gzip-NCD verdict (does NOT rewrite; the
                           caller runs the LLM rewrite loop on a reject)
  POST /micro/enforce   -> raise sentence-length CV (split/combine), paragraphs fixed
  POST /verify          -> humanization-step structural check (macro + micro)
  POST /lexical/inject  -> final-stage high-BCP swaps + human-sentence salt

voice_guard / orchestrator generation is LLM-driven and belongs in the existing
generation stage; it is not exposed here.

Run:  uvicorn content_pipeline.service.app:app --host 0.0.0.0 --port 8080
(install extras first:  pip install -e '.[service]')
"""
from __future__ import annotations

from typing import Optional

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except ImportError as e:                       # service extra not installed
    raise SystemExit("Install service deps: pip install -e '.[service]'") from e

from content_pipeline.macro_guardrail import macro
from content_pipeline.micro_guardrail import micro
from content_pipeline.lexical_injector import injector as lex

app = FastAPI(title="content-pipeline", version="0.1.0")


class TextIn(BaseModel):
    text: str
    ncd_min: Optional[float] = None
    cv_min: Optional[float] = None
    salt: bool = True


@app.post("/macro/evaluate")
def macro_evaluate(body: TextIn):
    r = macro.evaluate(body.text, body.ncd_min or macro.DEFAULT_NCD_MIN)
    return {"passed": r.passed, "ncd": r.ncd, "threshold": r.threshold,
            "paragraphs": r.paragraphs, "reason": r.reason}


@app.post("/micro/enforce")
def micro_enforce(body: TextIn):
    r = micro.enforce(body.text, body.cv_min or micro.DEFAULT_CV_MIN)
    return {"text": r.text, "cv_before": r.cv_before, "cv_after": r.cv_after,
            "passed": r.passed, "passes": r.passes,
            "paragraphs_in": r.paragraphs_in, "paragraphs_out": r.paragraphs_out,
            "note": r.note}


@app.post("/verify")
def verify(body: TextIn):
    """Humanization-step structural integrity: macro verdict + micro pass."""
    m = macro.evaluate(body.text, body.ncd_min or macro.DEFAULT_NCD_MIN)
    mic = micro.enforce(body.text, body.cv_min or micro.DEFAULT_CV_MIN)
    return {"macro_passed": m.passed, "macro_ncd": m.ncd,
            "micro_passed": mic.passed, "micro_cv": mic.cv_after,
            "text": mic.text,
            "structural_ok": m.passed and mic.passed and mic.paragraphs_in == mic.paragraphs_out}


@app.post("/lexical/inject")
def lexical_inject(body: TextIn):
    r = lex.inject(body.text, salt=body.salt)
    return {"text": r.text, "replacements": r.replacements,
            "salted_paragraphs": r.salted_paragraphs,
            "paragraphs_in": r.paragraphs_in, "paragraphs_out": r.paragraphs_out}


@app.get("/health")
def health():
    return {"ok": True}
