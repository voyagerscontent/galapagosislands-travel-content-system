"""
Optional lightweight Flask API to power the intake page.

Run:
    pip install flask flask-cors
    python -m humanizer.api

Endpoints:
    GET  /health
    GET  /rules            -> exported regex ruleset (for n8n / JS)
    POST /humanize         -> {"text": "..."}  returns HumanizeResult dict
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    from flask import Flask, jsonify, request, send_from_directory
    from flask_cors import CORS
except ImportError as e:  # pragma: no cover
    raise SystemExit("Flask not installed. Run: pip install flask flask-cors") from e

from .engine import Humanizer, MAX_WORDS

APP_ROOT = Path(__file__).resolve().parent.parent
INTAKE_DIR = APP_ROOT / "intake"

app = Flask(__name__, static_folder=str(INTAKE_DIR), static_url_path="")
CORS(app)

_h = Humanizer(max_words=MAX_WORDS)


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "dictionaries": _h.loaded_dictionaries,
        "entries": _h.total_entries(),
        "max_words": _h.max_words,
    })


@app.get("/rules")
def rules():
    return jsonify(_h.dump_regex_rules())


@app.post("/humanize")
def humanize():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not isinstance(text, str):
        return jsonify({"error": "text must be a string"}), 400
    result = _h.humanize(text)
    return jsonify(result.to_dict())


@app.get("/")
def index():
    return send_from_directory(str(INTAKE_DIR), "index.html")


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=8787, debug=False)
