"""Step 5b. Fold fragments into the longer candidate they belong to, and choose the pool to review.

A candidate B is a fragment of A when >= CONTAIN of B's occurrences overlap an occurrence of A and the two have about the
same number of occurrences (B has <= 1.25 A + 1, A has <= 2 B + 2): B is then just a piece of A (or A a variant
of B) and is not reported on its own. A is the candidate with larger n (then larger IC).
The pool for review keeps a candidate if it passes thresholds calibrated on the null model (see passes()):
  IC >= 24 bits, or IC >= 22 bits with >= 4 occurrences; >= 4 distinct pitches when n >= 7; occurrences >= 3 in
  >= 2 scenes (already true); not purely stepwise (> 90 % of intervals <= 2 semitones) unless the rhythm has
  contrast (>= 3x between its longest and shortest note). (The first version used stricter 28-30 bit cutoffs for
  short patterns; batches 01-06 were reviewed under it, tier 2 = the candidates added by the relaxed rule.)
Result: work/pool_v1.pkl + decisions/round1_ids.txt (the strict pool of review round 1) and work/pool.pkl (list of candidate dicts with "fragments": ids folded in) and results/pool_summary.txt.
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


def passes_v1(f):
    """The stricter first version of the thresholds, which defined the pool of review round 1 (batches 01-06)."""
    n, ic = f["n"], f["ic"]
    if n == 5 and ic < 30:
        return False
    if n in (6, 7) and ic < 28:
        return False
    if n >= 8 and ic < 24:
        return False
    if n >= 7 and f["pitches"] < 4:
        return False
    if f["stepwise"] > 0.9 and f["contrast"] < 3:
        return False
    return True


def passes(f):
    """Thresholds calibrated on the null model (explore/e10_null_by_ic.py): a seed with IC >= 24 bits, or with
    IC >= 22 bits and >= 4 occurrences, is essentially never chance (null: <= 7 per bin against >= 100 real)."""
    n, ic = f["n"], f["ic"]
    if not (ic >= 24 or (ic >= 22 and f["n_occ"] >= 4)):
        return False
    if n >= 7 and f["pitches"] < 4:
        return False
    if f["stepwise"] > 0.9 and f["contrast"] < 3:
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
    pool_v1 = [x for x in top if passes_v1(x["f"])]
    with open(os.path.join(WORK, "pool.pkl"), "wb") as fh:
        pickle.dump(pool, fh)
    with open(os.path.join(WORK, "pool_v1.pkl"), "wb") as fh:
        pickle.dump(pool_v1, fh)
    open(os.path.join(DECISIONS, "round1_ids.txt"), "w").write(" ".join(str(x["id"]) for x in pool_v1) + "\n")
    os.makedirs(RESULTS, exist_ok=True)
    tiers = Counter(x["tier"] for x in pool)
    lines = [f"candidates {len(cands)}; folded as fragments {len(parent)}; roots {len(top)}; pool after thresholds {len(pool)}",
             f"pool by tier: {dict(tiers)}",
             "pool by n: " + str(sorted(Counter(min(x['f']['n'], 20) for x in pool).items()))]
    open(os.path.join(RESULTS, "pool_summary.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
