"""Explore: how many pair+approximate candidates are new (not near ANY earlier candidate) and have contrasting rhythm?"""
import os, pickle, sys, collections
import numpy as np
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(root, "tools"))
import corpus
from common import WORK
c = corpus.load()
pairs = pickle.load(open(os.path.join(WORK, "pairs.pkl"), "rb"))
cands = pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))
by_act = collections.defaultdict(list)
for x in cands:
    for o in x["fam"]["occ"]:
        by_act[o["act"]].append((o["t0"] - 1, o["t1"] + 1))
new = []
for p in pairs:
    occ = p["fam"]["occ"]
    hit = sum(1 for o in occ if any(s <= o["t1"] and o["t0"] <= e for s, e in by_act[o["act"]]))
    w = p["seed"]["stm"][0][0]; n = p["seed"]["n"]
    q = np.round(c["ioi"][w:w + n - 1] * 24) / 24
    uniform = collections.Counter(q.tolist()).most_common(1)[0][1] / len(q)
    p["f"]["uniform"] = float(uniform)
    if hit / len(occ) < 0.5 and uniform < 0.85:
        new.append(p)
print(len(pairs), "pair candidates;", len(new), "new (<50% near any earlier candidate) with contrasting rhythm")
print("n dist", sorted(collections.Counter(min(p['f']['n'], 14) for p in new).items()))
print("extra statements dist", sorted(collections.Counter(len(p['fam']['occ']) - 2 for p in new).items()))
pickle.dump(new, open(os.path.join(WORK, "pairs_new.pkl"), "wb"))
