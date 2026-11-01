"""Explore: members of one group of decisions/groups_auto.tsv, one line each (id, n, occurrences, first notes, durations)."""
import os, pickle, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import corpus, dossier
from common import DECISIONS, WORK
lm = sys.argv[1]
c = corpus.load()
cands = {x["id"]: x for x in pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))}
for line in open(os.path.join(DECISIONS, "groups_auto.tsv"), encoding="utf-8").read().splitlines()[1:]:
    p = line.split("\t")
    if p[0] == lm:
        print("themes:", p[3][:300])
        for m in map(int, p[2].split(",")):
            x = cands[m]
            names, ioi = dossier.pattern_notes(c, x["seed"], x["seed"]["stm"][0][0])
            print(f"#{m} n={x['f']['n']} occ={x['f']['n_occ']} | {' '.join(names[:9])} | {' '.join(map(str, ioi[:8]))}")
