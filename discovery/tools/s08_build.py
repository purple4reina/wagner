"""Step 8. Build the published results from the grouped, accepted candidates.

For every group in decisions/groups_auto.tsv this writes results/leitmotifs/LMnnn.json and .md with the pattern and EVERY occurrence:
act, scene, measure range, streams it was found in, time in the Karajan1966 recording, the notes (as played there,
so the transposition is visible), the text sung at that moment, and whether the match is exact (found by the miner)
or approximate (found by s07_expand.py; with its distance). Also results/INDEX.md and results/occurrences.csv.
Occurrences = statements: windows that overlap or lie within GAP quarter notes of each other are one.
Run: discovery/.venv/bin/python -I discovery/tools/s08_build.py
"""
import csv
import json
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
import dossier
from common import ACTS, DECISIONS, OPERA, RESULTS, SHORT, WORK

GAP = 4.0


def read_groups():
    rows = {}
    for line in open(os.path.join(DECISIONS, "groups_auto.tsv"), encoding="utf-8").read().splitlines()[1:]:
        lm, rep, members, themes = (line.split("\t") + ["", "", "", ""])[:4]
        rows[lm] = dict(lm=lm, rep=int(rep), members=[int(x) for x in members.split(",")], themes=themes)
    return rows


def shape(members, cands):
    """Descriptive label, used only to arrange INDEX.md (nothing is excluded by it):
    "scalar" if most merged patterns are stepwise runs (>= 85 % of intervals within 2 semitones);
    "cell" if most are low in pitch variety (found only without the old pitch-variety rules, or >= 7 notes on < 4 pitches);
    else "melodic"."""
    if sum(cands[m]["f"]["stepwise"] >= 0.85 for m in members) >= 0.6 * len(members):
        return "scalar"
    low = [cands[m]["kind"].endswith("_simple") or (cands[m]["f"]["n"] >= 7 and cands[m]["f"]["pitches"] < 4) for m in members]
    return "cell" if sum(low) >= 0.6 * len(members) else "melodic"


def strength(ic, n_scenes, n_occ):
    """Statistical strength, not musical importance: how unlikely the pattern is by chance and how widely it recurs.
    strong: >= 35 bits and >= 4 scenes; medium: >= 28 bits and >= 3 occurrences; weak: the rest (still >= 22 bits)."""
    if ic >= 35 and n_scenes >= 4:
        return "strong"
    if ic >= 28 and n_occ >= 3:
        return "medium"
    return "weak"


def merged_occurrences(group, cands, expansions):
    occ = [dict(o, exact=True) for m in group["members"] for o in cands[m]["fam"]["occ"]]
    for m in group["members"]:
        ex = expansions.get(m)
        if ex and ex["kept"]:
            occ += [dict(o, exact=False) for o in ex["occ"]]
    occ.sort(key=lambda o: (o["act"], o["t0"]))
    out = []
    for o in occ:
        if out and out[-1]["act"] == o["act"] and o["t0"] <= out[-1]["t1"] + GAP:
            p = out[-1]
            p["t1"] = max(p["t1"], o["t1"])
            p["parts"] = p["parts"] + o["parts"]
            p["exact"] = p["exact"] or o["exact"]
            p["dist"] = min(p.get("dist", 9), o.get("dist", 9))
        else:
            out.append(dict(o, parts=list(o["parts"])))
    return out


def notes_of(c, o):
    w0, w1, _ = max(o["parts"], key=lambda p: p[1] - p[0])
    w1 = min(w1, w0 + 47)  # a long ostinato can span thousands of notes; keep the first 48
    return [dossier.note_name(int(c["pitch"][i]), int(c["dia"][i])) for i in range(w0, w1 + 1)], \
        [round(float(x), 2) for x in c["ioi"][w0:w1]]


def main():
    c = corpus.load()
    cands = {x["id"]: x for x in pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))}
    exp_path = os.path.join(WORK, "expansions.pkl")
    expansions = pickle.load(open(exp_path, "rb")) if os.path.exists(exp_path) else {}
    groups = read_groups()
    out_dir = os.path.join(RESULTS, "leitmotifs")
    os.makedirs(out_dir, exist_ok=True)
    for fn in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, fn))
    index, flat = [], []
    for lm, g in sorted(groups.items()):
        rep = cands[g["rep"]]
        names, ioi = dossier.pattern_notes(c, rep["seed"], rep["seed"]["stm"][0][0])
        occs = merged_occurrences(g, cands, expansions)
        rows = []
        for o in occs:
            r = dossier.occurrence_row(c, o)
            r["notes"], r["durations"] = notes_of(c, o)
            r["match"] = "exact" if o["exact"] else f"approximate (distance {o.get('dist', 0):.1f})"
            rows.append(r)
        scenes = {(r["act"], r["scene"]) for r in rows}
        acts = {r["act"] for r in rows}
        ops = {OPERA[a] for a in acts}
        n_exact = sum(1 for o in occs if o["exact"])
        data = dict(id=lm, n_notes=rep["f"]["n"], pattern_notes=names, pattern_durations=ioi,
                    pattern_intervals=[int(x) - (9 if rep["kind"].startswith("dint") else 15) for x in rep["seed"]["tokens"][0]],
                    n_occurrences=len(rows), n_exact=n_exact, n_scenes=len(scenes), n_acts=len(acts), n_operas=len(ops),
                    reviewer_themes=g["themes"], member_candidates=g["members"], occurrences=rows,
                    shape=shape(g["members"], cands), ic_bits=round(rep["f"]["ic"], 1), strength=strength(rep["f"]["ic"], len(scenes), len(rows)),
                    meets_criteria=bool(len(rows) >= 3 and len(scenes) >= 2 and rep["f"]["n"] >= 5))
        json.dump(data, open(os.path.join(out_dir, f"{lm}.json"), "w"), indent=1, ensure_ascii=False)
        md = [f"# {lm}", "",
              f"{data['n_notes']} notes, {len(rows)} occurrences ({n_exact} exact) in {len(scenes)} scenes, {len(acts)} acts, "
              f"{len(ops)} operas. Statistical strength: {data['strength']} ({data['ic_bits']} bits).", "",
              f"Notes (one occurrence): {' '.join(names)}", "", f"Durations (quarter notes): {' '.join(map(str, ioi))}", "",
              f"Intervals (semitones): {' '.join(f'{x:+d}' for x in data['pattern_intervals'])}", "",
              f"Reviewer hints (not names): {g['themes'] or '-'}", "",
              "| act | scene | measures | time (Karajan1966) | streams | match | sung text |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            md.append(f"| {r['act_short']} | {r['scene']} | {r['pos0']:.2f}-{r['pos1']:.2f} | {r['time']} | "
                      f"{','.join(r['streams'])} | {r['match']} | {r['text'].replace('|', '/')[:160]} |")
            flat.append([lm, r["act_short"], r["scene"], f"{r['pos0']:.3f}", f"{r['pos1']:.3f}", r["time"],
                         ",".join(r["streams"]), r["match"], " ".join(r["notes"]), r["text"]])
        open(os.path.join(out_dir, f"{lm}.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
        first = rows[0]
        index.append((data["shape"], data["strength"], lm, f"| [{lm}](leitmotifs/{lm}.md) | {data['strength']} | {data['n_notes']} | {len(rows)} | {len(scenes)} | "
                     f"{''.join(sorted(ops))} | {first['act_short']} m{first['measure']} | {g['themes'][:70]} |"))
    rank = {"strong": 0, "medium": 1, "weak": 2}
    head = ("| id | strength | notes | occurrences | scenes | ops | first at | reviewer hints |\n"
            "|---|---|---|---|---|---|---|---|\n")
    with open(os.path.join(RESULTS, "INDEX.md"), "w", encoding="utf-8") as fh:
        fh.write("# Leitmotifs found\n\nops: A Rheingold, B Walkure, C Siegfried, D Gotterdammerung. "
                 "Themes are hints from the reviewers, not names. Sorted by statistical strength, then by id (= pattern "
                 "length, longer first); `weak` ones are still far above chance but short or rare.\n")
        for sh, title in (("melodic", "Melodic patterns"),
                          ("scalar", "Scale-like patterns (mostly stepwise runs; listed apart because a scale is a shared idiom)"),
                          ("cell", "Repeated-cell patterns (few distinct pitches: tremolos, ostinati, trills; included because the "
                                   "criteria do not require different pitches)")):
            rows = sorted((t for t in index if t[0] == sh), key=lambda t: (rank[t[1]], t[2]))
            fh.write(f"\n## {title}: {len(rows)}\n\n{head}" + "\n".join(t[3] for t in rows) + "\n")
    with open(os.path.join(RESULTS, "occurrences.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["leitmotif", "act", "scene", "measure_start", "measure_end", "time_karajan1966", "streams", "match",
                    "notes", "sung_text"])
        w.writerows(flat)
    print(f"{len(groups)} leitmotifs written to {out_dir}")


if __name__ == "__main__":
    main()
