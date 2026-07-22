"""
human-dictionary-travel — deterministic AI-quirk to human replacement.

Public API:
    from humanizer import Humanizer
    h = Humanizer()
    result = h.humanize("Embark on a journey to delve into...")
    print(result.text)
    print(result.replacements)
"""

from .engine import Humanizer, Replacement, HumanizeResult, MAX_WORDS

__all__ = ["Humanizer", "Replacement", "HumanizeResult", "MAX_WORDS"]
__version__ = "1.0.0"
