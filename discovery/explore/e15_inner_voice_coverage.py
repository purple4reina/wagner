"""Explore: are the inner-voice families (work_inner/) located where baseline candidates (work/) already are?"""
import os, pickle, sys, collections
import numpy as np
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(root, "tools"))
from common import ACTS, SHORT
base = pickle.load(open(os.path.join(root, "work", "candidates.pkl"), "rb"))
by_act = collections.defaultdict(list)
for x in base:
    for o in x["fam"]["occ"]:
        by_act[o["act"]].append((o["t0"] - 1, o["t1"] + 1))
z = np.load(os.path.join(root, "work_inner", "corpus.npz"))
seeds = pickle.load(open(os.path.join(root, "work_inner", "seeds_semi.pkl"), "rb"))
fams = pickle.load(open(os.path.join(root, "work_inner", "families_semi.pkl"), "rb"))
free = []
for f in fams:
    hit = sum(1 for o in f["occ"] if any(s <= o["t1"] and o["t0"] <= e for s, e in by_act[o["act"]]))
    if hit / len(f["occ"]) < 0.5:
        free.append(f)
print(len(fams), "inner families;", len(free), "mostly outside every baseline candidate")
for f in sorted(free, key=lambda f: -seeds[f["rep"]]["n"])[:10]:
    sd = seeds[f["rep"]]
    print(" n=%d ic=%.0f occ=%d scenes=%d ops=%d at %s" % (sd["n"], sd["ic"], len(f["occ"]), f["n_scenes"], f["n_operas"],
          ", ".join(f"{SHORT[ACTS[o['act']]]}:{int(z['measure'][o['parts'][0][0]])}" for o in f["occ"][:5])))
