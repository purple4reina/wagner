"""Step 9. List what the reviewers excluded, and why, so nothing is dropped silently.

Candidates labelled S ("stock figure": a bare scale run, a bare broken chord of one chord, a trill, a bare cadence formula)
in review round 3, and candidates labelled G (generic idiom) in rounds 1-2 that round 3 did not re-review. Nothing is
excluded for its rhythm: the reviewers never saw durations in round 3.
Writes results/excluded_stock.tsv. Run: discovery/.venv/bin/python -I discovery/tools/s09_excluded_list.py
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
import dossier
from common import ACTS, RESULTS, SHORT, WORK
from s07b_group import load_verdicts


def main():
    c = corpus.load()
    cands = {x["id"]: x for x in pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))}
    rows = [(i, v) for i, v in sorted(load_verdicts().items()) if v["label"] in ("S", "G") and i in cands]
    with open(os.path.join(RESULTS, "excluded_stock.tsv"), "w", encoding="utf-8") as fh:
        fh.write("candidate\tlabel\treviewer_reason\tnotes\tn\toccurrences\tscenes\toperas\tfirst_locations\n")
        for i, v in rows:
            x = cands[i]
            names, _ = dossier.pattern_notes(c, x["seed"], x["seed"]["stm"][0][0])
            locs = ", ".join(f"{SHORT[ACTS[o['act']]]}:{int(c['measure'][o['parts'][0][0]])}" for o in x["fam"]["occ"][:6])
            f = x["f"]
            fh.write(f"{i}\t{v['label']}\t{v['theme']}\t{' '.join(names[:14])}\t{f['n']}\t{f['n_occ']}\t{f['n_scenes']}\t"
                     f"{f['n_operas']}\t{locs}\n")
    print(len(rows), "excluded candidates listed in results/excluded_stock.tsv")


if __name__ == "__main__":
    main()
