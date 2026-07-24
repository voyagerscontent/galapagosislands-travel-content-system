#!/usr/bin/env python3
"""Build data/lexicon.json from the High-Entropy Injectors (BCP) workbook.

The workbook's "All Words" sheet has columns: Word, Word Type, Category, Group.
Group is exactly destination / activity / feeling. We compile per-(group,
category) POS pools that lexical_injector uses to swap generic adjectives/verbs
for contextually-mapped high-BCP words. Re-run when the workbook changes:

  python content-pipeline/data/build_lexicon_from_xlsx.py "/path/to/High-Entropy Injectors (2.5-4.0 BPC).xlsx"
"""
import json
import os
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "lexicon.json")

# Generic, high-probability words the injector targets for replacement.
GENERIC_ADJECTIVES = [
    "beautiful", "stunning", "amazing", "incredible", "breathtaking", "gorgeous",
    "lovely", "nice", "great", "wonderful", "spectacular", "magnificent", "majestic",
    "pristine", "lush", "vast", "remote", "peaceful", "serene", "tranquil", "dramatic",
    "rugged", "vibrant", "memorable", "unforgettable", "picturesque", "scenic",
    "impressive", "striking", "charming", "idyllic", "pretty", "beautifull",
]
GENERIC_VERBS = [
    "see", "explore", "enjoy", "experience", "discover", "offer", "witness", "watch",
    "visit", "find", "observe", "encounter", "spot", "provide", "feel", "take in",
]

# WordType -> pool bucket
TYPE_MAP = {"Adjective": "adjective", "Sensory": "sensory", "Verb": "verb",
            "Noun": "noun", "Place": "place"}
GROUP_MAP = {"Destination": "destination", "Activity": "activity", "Feeling": "feeling"}


def main(xlsx: str):
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb["All Words"]
    pools = {"destination": {}, "activity": {}, "feeling": {}}
    counts = collections.Counter()
    for word, wtype, category, group in ws.iter_rows(min_row=2, values_only=True):
        if not (word and wtype and category and group):
            continue
        g = GROUP_MAP.get(str(group).strip())
        bucket = TYPE_MAP.get(str(wtype).strip())
        if not g or not bucket:
            continue
        cat = str(category).strip()
        w = str(word).strip()
        pools[g].setdefault(cat, {"adjective": [], "sensory": [], "verb": [], "noun": [], "place": []})
        if w not in pools[g][cat][bucket]:
            pools[g][cat][bucket].append(w)
            counts[bucket] += 1

    out = {
        "_meta": {
            "name": "high_bcp_lexicon",
            "description": "High-BCP (2.5-4.0 BPC) travel vocabulary compiled from the "
                           "High-Entropy Injectors workbook, categorized by destination / "
                           "activity / feeling and POS. Used by lexical_injector to swap generic "
                           "adjectives/verbs for contextually-mapped low-probability words.",
            "source": os.path.basename(xlsx),
            "version": "1.0.0",
            "totals": dict(counts),
        },
        "generic_adjectives": GENERIC_ADJECTIVES,
        "generic_verbs": GENERIC_VERBS,
        "pools": pools,
        # verbatim human "salt" sentences are a separate database — seed kept from v0.
        "human_sentences": [
            {"text": "You forget your phone exists out there, and it takes a day to notice.", "tags": ["feeling", "general"]},
            {"text": "Bring a dry bag; the wet landings soak everything you love.", "tags": ["activity", "packing"]},
            {"text": "The sea lions do not care that you paid to be there.", "tags": ["wildlife", "feeling"]},
            {"text": "Half the trip is the panga rides between the good stuff.", "tags": ["activity", "cruise"]},
            {"text": "Nobody warns you how loud the frigatebirds get at dawn.", "tags": ["wildlife", "destination"]},
            {"text": "The water is colder than the brochures let on, even in a wetsuit.", "tags": ["activity", "snorkel"]},
            {"text": "You will run out of adjectives by day three; stop trying.", "tags": ["feeling", "general"]}
        ],
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    ncats = sum(len(v) for v in pools.values())
    print(f"wrote {OUT}: {ncats} categories, pools {dict(counts)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: build_lexicon_from_xlsx.py <xlsx path>")
    main(sys.argv[1])
