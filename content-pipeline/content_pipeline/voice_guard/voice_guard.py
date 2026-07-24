"""voice_guard — the pipeline entry point (Step 1).

Two jobs:
1. Build the SYSTEM PROMPT that fixes the author's voice parameters, with all the
   existing guardrails, the master info file, and the Guardian of Truth loaded and
   HARDCODED in (nothing about them is negotiable per section).
2. Drive generation ONE SECTION AT A TIME (300–600 words each) instead of asking
   the model for the whole article at once — so every section can be gated by
   macro_guardrail immediately after it is produced.

The LLM itself is injected as a callable, so this module has no model/network
dependency and is unit-testable. The orchestrator wires the per-section macro
check + rewrite loop around what this module yields.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

SECTION_MIN_WORDS = 300
SECTION_MAX_WORDS = 600

# Repo context-pack (source of truth for voice + guardrails). Overridable.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_CP = os.path.join(_REPO_ROOT, "context-pack")

# The hardcoded blocks that must be present in EVERY system prompt, in order.
VOICE_FILE = os.path.join(_CP, "brand-voice", "AUTHOR_VOICE.juan-magallanes.md")
MASTER_FILE = os.path.join(_CP, "MASTER_FACTS_FILE.md")
GUARDIAN_FILE = os.path.join(_CP, "guardrails", "GUARDIAN_OF_TRUTH.md")
GUARDRAILS_GLOB = os.path.join(_CP, "guardrails", "*.md")


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


@dataclass
class VoiceConfig:
    voice_file: str = VOICE_FILE
    master_file: str = MASTER_FILE
    guardian_file: str = GUARDIAN_FILE
    guardrails_glob: str = GUARDRAILS_GLOB
    section_min: int = SECTION_MIN_WORDS
    section_max: int = SECTION_MAX_WORDS


def load_blocks(cfg: VoiceConfig) -> Dict[str, str]:
    """Load the hardcoded voice/guardrail/master/guardian blocks from disk."""
    guardrails = []
    for p in sorted(glob.glob(cfg.guardrails_glob)):
        if os.path.abspath(p) == os.path.abspath(cfg.guardian_file):
            continue                      # guardian is emitted as its own block
        guardrails.append(_read(p))
    return {
        "voice": _read(cfg.voice_file),
        "master": _read(cfg.master_file),
        "guardian": _read(cfg.guardian_file),
        "guardrails": "\n\n".join(g for g in guardrails if g),
    }


def build_system_prompt(cfg: Optional[VoiceConfig] = None, blocks: Optional[dict] = None) -> str:
    """Assemble the system prompt: voice parameters + ALL guardrails + master info
    + Guardian of Truth, plus the one-section-at-a-time generation contract."""
    cfg = cfg or VoiceConfig()
    b = blocks or load_blocks(cfg)
    return "\n\n".join([
        "=== AUTHOR VOICE (fixed parameters — write in this voice, always) ===",
        b["voice"] or "(voice file missing)",
        "=== GUARDIAN OF TRUTH (hardcoded — every claim must comply) ===",
        b["guardian"] or "(guardian file missing)",
        "=== MASTER INFO FILE (source of truth for facts) ===",
        b["master"] or "(master file missing)",
        "=== GUARDRAILS (all hardcoded, apply to every section) ===",
        b["guardrails"] or "(no guardrails found)",
        "=== GENERATION CONTRACT ===\n"
        f"Write the article ONE SECTION AT A TIME. Produce ONLY the single section "
        f"you are asked for — never the whole article. Each section MUST be between "
        f"{cfg.section_min} and {cfg.section_max} words of body prose. Vary paragraph "
        f"length and sentence rhythm deliberately (human burstiness). Do not restate "
        f"the brief, do not add headings you were not asked for, do not write a "
        f"conclusion unless the section IS the conclusion. Obey the voice, the "
        f"Guardian of Truth, the master facts, and every guardrail above.",
    ])


@dataclass
class Section:
    key: str
    title: str
    text: str = ""
    word_count: int = 0
    within_range: bool = False


def _wc(text: str) -> int:
    return len(text.split())


def generate_section(section_spec: dict, system_prompt: str,
                     llm: Callable[[str, str], str], cfg: VoiceConfig,
                     context: str = "") -> Section:
    """Generate ONE section (300–600 words) via the injected llm(system, user)."""
    user = (f"SECTION TO WRITE: {section_spec.get('title', section_spec['key'])}\n"
            f"What this section must cover: {section_spec.get('brief', '')}\n"
            + (f"Already-written context (do not repeat): {context[-1500:]}\n" if context else "")
            + f"Write {cfg.section_min}-{cfg.section_max} words. Only this section.")
    text = (llm(system_prompt, user) or "").strip()
    wc = _wc(text)
    return Section(section_spec["key"], section_spec.get("title", section_spec["key"]),
                   text, wc, cfg.section_min <= wc <= cfg.section_max)


def generate_article(outline: List[dict], llm: Callable[[str, str], str],
                     cfg: Optional[VoiceConfig] = None,
                     on_section: Optional[Callable[[Section], Section]] = None) -> List[Section]:
    """Generate every section in the outline, one at a time.

    `on_section` (optional) is the orchestrator hook that runs macro_guardrail +
    its rewrite loop on each freshly-generated section before it is accepted and
    used as context for the next one.
    """
    cfg = cfg or VoiceConfig()
    system_prompt = build_system_prompt(cfg)
    sections: List[Section] = []
    context = ""
    for spec in outline:
        sec = generate_section(spec, system_prompt, llm, cfg, context)
        if on_section is not None:
            sec = on_section(sec)
        sections.append(sec)
        context += "\n\n" + sec.text
    return sections
