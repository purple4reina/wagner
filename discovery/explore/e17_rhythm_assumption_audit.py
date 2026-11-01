"""Audit: what did the rhythm-variety assumptions exclude?  (Written after the user pointed out that the rhythm
criterion is about consistency between occurrences, not about variety inside a motif.)
Run: discovery/.venv/bin/python -I discovery/explore/e17_rhythm_assumption_audit.py
"""
import collections, os, pickle, sys
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(root, "tools"))
from common import WORK
from s07b_group import load_verdicts
import s05b_reduce
cands = pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))
pool = {x["id"]: x for x in pickle.load(open(os.path.join(WORK, "pool.pkl"), "rb"))}
v = load_verdicts()
print("pool", len(pool), "by tier x label:")
t = collections.Counter((x["tier"], v.get(i, {}).get("label", "-")) for i, x in pool.items())
for k in sorted(t): print("  ", k, t[k])
# candidates that the IC/length thresholds would keep but the contrast clause removed
frag = {f for x in cands for f in x.get("fragments", [])}
def ic_ok(f):
    return f["ic"] >= 24 or (f["ic"] >= 22 and f["n_occ"] >= 4)
dropped = [x for x in cands if x["id"] not in frag and ic_ok(x["f"]) and not (x["f"]["n"] >= 7 and x["f"]["pitches"] < 4)
           and x["f"]["stepwise"] > 0.9 and x["f"]["contrast"] < 3]
print("removed only by the 'stepwise > 0.9 and contrast < 3' clause:", len(dropped))
print("  by n:", sorted(collections.Counter(min(x['f']['n'], 14) for x in dropped).items()))
