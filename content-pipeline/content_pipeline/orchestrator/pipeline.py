"""orchestrator — wires the strictly-separated modules in the required order.

Per the spec:
  Step 1  voice_guard        generate ONE section at a time (300–600 words)
  Step 2  macro_guardrail    immediately gate each section (gzip NCD); on reject,
                             LLM rewrite loop (max_retries=3)
  Step 3  micro_guardrail    raise sentence-length CV (split/combine), paragraphs fixed
          ...assemble the article...
  Step 4  humanization       humanize ONE PROSE BLOCK AT A TIME via structure_guard
                             (skeleton locked: headings + paragraph count fixed), then
                             micro re-tightens and a gate verifies the skeleton held
  Step 5  lexical_injector   ABSOLUTE END — inject high-BCP words + human salt so no
                             later pass can overwrite the low-probability tokens

All external effects (LLM generate, LLM rewrite, the existing humanize step) are
injected callables, so the whole pipeline is deterministic and testable without a
model. Downstream, the caller continues with the already-proven steps and audits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from content_pipeline.voice_guard import voice_guard as vg
from content_pipeline.macro_guardrail import macro as macro_mod
from content_pipeline.micro_guardrail import micro as micro_mod
from content_pipeline.lexical_injector import injector as lex_mod
from content_pipeline.structure_guard import structure_guard

# Injected callables
LLM = Callable[[str, str], str]                 # (system_prompt, user_prompt) -> text
Rewrite = Callable[[str, macro_mod.MacroResult], str]
Humanize = Callable[[str], str]


@dataclass
class SectionRun:
    key: str
    text: str
    macro: macro_mod.MacroResult
    macro_attempts: int
    micro: micro_mod.MicroResult


@dataclass
class PipelineResult:
    article: str
    sections: List[SectionRun] = field(default_factory=list)
    humanize_macro: List[macro_mod.MacroResult] = field(default_factory=list)
    humanize_micro: List[micro_mod.MicroResult] = field(default_factory=list)
    injection: Optional[lex_mod.InjectionResult] = None
    flags: List[str] = field(default_factory=list)


def _gate_section(text: str, rewrite: Rewrite, cfg) -> SectionRun:
    # Step 2: macro NCD gate + rewrite loop (max_retries handled in macro.enforce)
    text, mres, attempts = macro_mod.enforce(text, rewrite, max_retries=macro_mod.MAX_RETRIES)
    # Step 3: micro CV (paragraph-preserving)
    mic = micro_mod.enforce(text)
    return SectionRun("", mic.text, mres, attempts, mic)


def run(outline: List[dict], llm: LLM, rewrite: Rewrite,
        humanize: Optional[Humanize] = None,
        cfg: Optional[vg.VoiceConfig] = None,
        lexicon: Optional[dict] = None) -> PipelineResult:
    cfg = cfg or vg.VoiceConfig()
    result = PipelineResult(article="")

    # Steps 1–3: generate each section, then gate it immediately.
    def on_section(sec: vg.Section) -> vg.Section:
        run_ = _gate_section(sec.text, rewrite, cfg)
        run_.key = sec.key
        result.sections.append(run_)
        if not run_.macro.passed:
            result.flags.append(f"section '{sec.key}': macro still failing after "
                                 f"{run_.macro_attempts} rewrites (NCD {run_.macro.ncd})")
        if not run_.micro.passed:
            result.flags.append(f"section '{sec.key}': micro CV {run_.micro.cv_after} "
                                 f"< {run_.micro.threshold}")
        sec.text = run_.text
        return sec

    vg.generate_article(outline, llm, cfg, on_section=on_section)
    article = "\n\n".join(s.text for s in result.sections)

    # Step 4: humanization with the optimized SKELETON LOCKED (structure_guard).
    # The humanizer rewrites ONE PROSE BLOCK AT A TIME; headings and the paragraph
    # count are preserved by construction, so it can no longer collapse the macro /
    # micro burstiness established in steps 2-3. micro re-tightens within the locked
    # paragraphs and a deterministic gate confirms the skeleton is intact.
    if humanize is not None:
        guarded = structure_guard.guarded_humanization(article, humanize)
        article = guarded["text"]
        report = guarded["structure"]
        result.humanize_macro.append(macro_mod.evaluate(article))
        result.humanize_micro.append(guarded["micro"])
        if not report["passed"]:
            result.flags.append("post-humanize structure/burstiness lost: "
                                + "; ".join(report["reasons"]))

    # Step 5: lexical injection — ABSOLUTE END (nothing rewrites after this).
    inj = lex_mod.inject(article, lexicon)
    result.injection = inj
    result.article = inj.text
    return result
