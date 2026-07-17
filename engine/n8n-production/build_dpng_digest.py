#!/usr/bin/env python3
"""Generate DPNG_VISITOR_SITES.md — the 210 official visitor sites, in a form a prompt can read.

Why: MASTER_FACTS_FILE lists galapagos_master.xlsx as an authoritative source and tells the
writer to "cite the file/sheet inline" — but the workbook never reaches the prompt. Only the two
.md fact files do. So the model was being told to cite data it cannot see. It filled the gap from
training and invented a [source:] tag: the iguana draft cited 'Cerro Dragon' as a Santa Cruz site
with [source: §2 Islands — Santa Cruz]. Cerro Dragon IS a real DPNG site — it is row 10 of the
Santa Cruz sites in this very workbook — but Truth Check could not verify it and correctly failed
the page. The fix is not to loosen Truth Check; it is to put the data in front of the model.

Emits a compact digest (island -> sites, type, permitted activities) rather than the raw 23-column
grid, so it stays small enough to load. Regenerate whenever the DPNG sheet changes.

Context-scoped: loaded for wildlife / island / visitor-site / itinerary / hub pages, not for a
budget guide. Irrelevant data is padding.
"""
import openpyxl, os, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "context-pack/what-to-write-about/source-of-truth/galapagos_master.xlsx")
OUT = os.path.join(ROOT, "context-pack/what-to-write-about/source-of-truth/DPNG_VISITOR_SITES.md")

wb = openpyxl.load_workbook(SRC, read_only=True)
ws = wb["DPNG Site Activities"]
rows = ws.iter_rows(values_only=True)
hdr = [str(h) if h is not None else "" for h in next(rows)]

ACT = {"SN": "snorkel", "PR": "panga ride", "KY_TR": "kayak", "SC": "dive", "BI": "instructional dive",
       "BN": "night dive", "CD": "check dive", "CN": "circumnavigation", "S": "surf",
       "ESP": "recreation", "CA": "walk", "CP": "camping", "BK": "cycling"}
iI, iS, iT, iN = hdr.index("Isla"), hdr.index("Sitio"), hdr.index("Tipo"), hdr.index("Nomenclatura")
iCUP = hdr.index("CUP") if "CUP" in hdr else None
iCAV = hdr.index("CAV") if "CAV" in hdr else None
acols = {c: hdr.index(c) for c in ACT if c in hdr}

islands = collections.OrderedDict()
n = 0
for row in rows:
    isla = str(row[iI] or "").strip()
    sitio = str(row[iS] or "").strip()
    if not isla or not sitio:
        continue
    # the sheet marks a permitted activity with an uppercase 'X'; blank means not permitted
    acts = [ACT[c] for c, i in acols.items() if str(row[i] or "").strip().upper() == "X"]
    cup = row[iCUP] if iCUP is not None else None
    cav = row[iCAV] if iCAV is not None else None
    islands.setdefault(isla, []).append(
        (sitio, str(row[iT] or "").strip(), str(row[iN] or "").strip(), acts, cup, cav))
    n += 1

L = []
L.append("# DPNG VISITOR SITES — the official list (authoritative)\n")
L.append("Source: Galápagos National Park Directorate (DPNG) / Fundación Charles Darwin visitor-site")
L.append("dataset, mirrored in `source-of-truth/galapagos_master.xlsx` sheet `DPNG Site Activities`.")
L.append("**%d sites across %d islands.** Cite as `[source: DPNG Site Activities]`.\n" % (n, len(islands)))
L.append("## Rules for using this list\n")
L.append("1. **A site not on this list does not exist.** Never name a visitor site that is not here.")
L.append("2. **Never invent an activity for a site.** If snorkelling is not listed for a site, do not")
L.append("   say you can snorkel there. The activity columns are the permitted-use record.")
L.append("3. `M` = marine site, `T` = terrestrial. Every site is a National Park visitor site: a")
L.append("   GNPS-certified naturalist guide is required, and wildlife-distance rules apply.")
L.append("4. Presence of a site says nothing about which vessels visit it — that is itinerary data.")
L.append("5. This list is *sites*, not species. It does not license a wildlife claim: do not say an")
L.append("   animal is at a site unless a fact file says so.")
L.append("6. `quota` is the DPNG's published site quota (CUP) and `capacity` its visitor")
L.append("   carrying-capacity metric (CAV). Quote them only as the Park's own operational figures.\n")
L.append("## Sites by island\n")
for isla in sorted(islands):
    sites = islands[isla]
    L.append("### %s (%d sites)\n" % (isla, len(sites)))
    for sitio, tipo, nom, acts, cup, cav in sorted(sites):
        a = ", ".join(acts) if acts else "no activities flagged"
        q = []
        if cup not in (None, ""):
            q.append("quota %s" % cup)
        if cav not in (None, ""):
            q.append("capacity %s" % cav)
        qs = "; " + ", ".join(q) if q else ""
        L.append("- **%s** (%s%s) — %s%s" % (sitio, tipo or "?", ", " + nom if nom else "", a, qs))
    L.append("")

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("wrote %s" % os.path.relpath(OUT, ROOT))
print("   %d sites, %d islands, %d lines, %d chars" % (n, len(islands), len(L), len("\n".join(L))))
wb.close()
