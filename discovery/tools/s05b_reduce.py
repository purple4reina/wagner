"""Step 5b. Fold fragments into the longer candidate they belong to, and choose the pool to review.

A candidate B is a fragment of A when >= CONTAIN of B's occurrences overlap an occurrence of A and the two have about the
same number of occurrences (B has <= 1.25 A + 1, A has <= 2 B + 2): B is then just a piece of A (or A a variant
of B) and is not reported on its own. A is the candidate with larger n (then larger IC).
The pool for review keeps a candidate if it passes thresholds calibrated on the null model (see passes()):
  IC >= 24 bits, or IC >= 22 bits with >= 4 occurrences; occurrences >= 3 in >= 2 scenes (already true).
  Nothing here looks at the variety of durations OR OF PITCHES inside a pattern: the user's rhythm
  criterion is about occurrences matching each other, not about a motif having long and short notes.
  (Review round 1 used a stricter version -- 28-30 bit cutoffs for short patterns and a clause that dropped stepwise
  patterns with little duration contrast. That clause was a mistake and is gone; decisions/round1_ids.txt, the list round 1
  reviewed, is kept as a frozen historical record and is no longer regenerated.)
Result: work/pool.pkl (list of candidate dicts with "fragments": ids folded in) and results/pool_summary.txt.
Run: discovery/.venv/bin/python -I discovery/tools/s05b_reduce.py
"""
import os
import pickle
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DECISIONS, RESULTS, WORK

CONTAIN = 0.8
SLACK = 1.0


def passes(f):
    """Thresholds calibrated on the null model (explore/e10_null_by_ic.py): a seed with IC >= 24 bits, or with
    IC >= 22 bits and >= 4 occurrences, is essentially never chance (null: <= 7 per bin against >= 100 real)."""
    n, ic = f["n"], f["ic"]
    if not (ic >= 24 or (ic >= 22 and f["n_occ"] >= 4)):
        return False
    return True


def main():
    cands = pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))
    order = sorted(cands, key=lambda x: (-x["f"]["n"], -x["f"]["ic"]))
    by_act = {}
    for x in order:
        for o in x["fam"]["occ"]:
            by_act.setdefault(o["act"], []).append((o["t0"] - SLACK, o["t1"] + SLACK, x["id"]))
    byid = {x["id"]: x for x in cands}
    rank = {x["id"]: i for i, x in enumerate(order)}
    parent = {}
    for x in order:
        near = Counter()
        for o in x["fam"]["occ"]:
            seen = set()
            for s, e, i in by_act.get(o["act"], ()):
                if i != x["id"] and rank[i] < rank[x["id"]] and s <= o["t1"] and o["t0"] <= e and i not in seen:
                    seen.add(i)
                    near[i] += 1
        nb, best = x["f"]["n_occ"], None
        for i, k in near.most_common():
            na = byid[i]["f"]["n_occ"]
            if k >= CONTAIN * nb and nb <= 1.25 * na + 1 and na <= 2 * nb + 2:
                best = i
                break
        if best is not None:
            while best in parent:
                best = parent[best]
            parent[x["id"]] = best
    for x in cands:
        x["fragments"] = []
    for child, par in parent.items():
        byid[par]["fragments"].append(child)
    top = [x for x in order if x["id"] not in parent]
    pool = [x for x in top if passes(x["f"])]
    with open(os.path.join(WORK, "pool.pkl"), "wb") as fh:
        pickle.dump(pool, fh)
    os.makedirs(RESULTS, exist_ok=True)
    lines = [f"candidates {len(cands)}; folded as fragments {len(parent)}; roots {len(top)}; pool after thresholds {len(pool)}",
             "pool by n: " + str(sorted(Counter(min(x['f']['n'], 20) for x in pool).items()))]
    open(os.path.join(RESULTS, "pool_summary.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
