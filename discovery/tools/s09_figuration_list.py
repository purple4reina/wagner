"""Step 9. List the recurring figuration (uniform-rhythm patterns) that the leitmotif list leaves out, for transparency.

Figuration = at least 85 % of the pattern's notes have the same duration (tier "figuration" in s05_candidates.py).
The user's criteria ask for some notes long and others short, so these are not reported as leitmotifs, but they recur
(e.g. wave arpeggios) and someone may want them. Writes results/figuration.tsv, one line per candidate of the review
pool with the first occurrence and a few more; ordered by spread (operas, then occurrences).
Run: discovery/.venv/bin/python -I discovery/tools/s09_figuration_list.py
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
import dossier
from common import RESULTS, SHORT, ACTS, WORK


def main():
    c = corpus.load()
    pool = [x for x in pickle.load(open(os.path.join(WORK, "pool.pkl"), "rb")) if x["tier"] == "figuration"]
    pool.sort(key=lambda x: (-x["f"]["n_operas"], -x["f"]["n_occ"], -x["f"]["n"]))
    with open(os.path.join(RESULTS, "figuration.tsv"), "w", encoding="utf-8") as fh:
        fh.write("candidate\tnotes\tn\toccurrences\tscenes\toperas\tduration\tfirst_locations\n")
        for x in pool:
            names, ioi = dossier.pattern_notes(c, x["seed"], x["seed"]["stm"][0][0])
            locs = ", ".join(f"{SHORT[ACTS[o['act']]]}:{int(c['measure'][o['parts'][0][0]])}" for o in x["fam"]["occ"][:6])
            f = x["f"]
            fh.write(f"{x['id']}\t{' '.join(names[:14])}\t{f['n']}\t{f['n_occ']}\t{f['n_scenes']}\t{f['n_operas']}\t"
                     f"{ioi[0] if ioi else ''}\t{locs}\n")
    print(len(pool), "figuration candidates listed in results/figuration.tsv")


if __name__ == "__main__":
    main()
