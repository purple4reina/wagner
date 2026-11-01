"""Explore: do long rhythm-agnostic families (n >= 14) cover places that no existing candidate covers?"""
import os, pickle, sys, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import corpus
from common import WORK, ACTS, SHORT
c = corpus.load()
seeds = pickle.load(open(os.path.join(WORK, "seeds_semi_nr.pkl"), "rb"))
fams = [f for f in pickle.load(open(os.path.join(WORK, "families_semi_nr.pkl"), "rb")) if seeds[f["rep"]]["n"] >= 14]
cands = pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))
by_act = collections.defaultdict(list)
for x in cands:
    for o in x["fam"]["occ"]:
        by_act[o["act"]].append((o["t0"] - 1, o["t1"] + 1))
free = []
for f in fams:
    hit = sum(1 for o in f["occ"] if any(s <= o["t1"] and o["t0"] <= e for s, e in by_act[o["act"]]))
    if hit / len(f["occ"]) < 0.6:
        free.append(f)
print(len(fams), "long nr families;", len(free), "not covered (< 60 % of occurrences near an existing candidate)")
for f in free[:12]:
    sd = seeds[f["rep"]]
    print(" n=%d ic=%.0f occ=%d scenes=%d ops=%d at %s" % (sd["n"], sd["ic"], len(f["occ"]), f["n_scenes"], f["n_operas"],
          ", ".join(f"{SHORT[ACTS[o['act']]]}:{int(c['measure'][o['parts'][0][0]])}" for o in f["occ"][:5])))
