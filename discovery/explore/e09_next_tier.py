"""Explore: size of the candidates that the review pool thresholds left out (the "next tier")."""
import os, pickle, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from common import WORK
cands = pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))
pool = {x["id"] for x in pickle.load(open(os.path.join(WORK, "pool.pkl"), "rb"))}
frag = {f for x in cands for f in x.get("fragments", [])}
rest = [x for x in cands if x["id"] not in pool and x["id"] not in frag]
print(len(rest), "not in pool and not fragments")
for name, cond in [("n>=6", lambda f: f["n"] >= 6), ("n>=6 occ>=4", lambda f: f["n"] >= 6 and f["n_occ"] >= 4),
                   ("n>=6 occ>=4 ops>=2 ic>=22", lambda f: f["n"] >= 6 and f["n_occ"] >= 4 and f["n_operas"] >= 2 and f["ic"] >= 22),
                   ("n>=5 ic>=26 occ>=4", lambda f: f["n"] >= 5 and f["ic"] >= 26 and f["n_occ"] >= 4),
                   ("contrast>=3 n>=6", lambda f: f["n"] >= 6 and f["contrast"] >= 3 and f["ic"] >= 22)]:
    print(name, sum(cond(x["f"]) for x in rest))
