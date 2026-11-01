"""Step 7. Find approximate occurrences of accepted motifs, guarded by the null model.

The exact miner needs identical (interval, rhythm-class) windows, so a statement with one changed note or a
slightly different rhythm is missed. For each accepted candidate we scan every window of the same length n in the
corpus and compute a distance to the representative occurrence:
    D_int = sum over the n-1 intervals of  0 (same) / 0.5 (differs by 1 semitone: mode or chromatic variant) / 1 (other)
    D_rc  = sum over the n-2 rhythm classes of  min(|class difference|, 2) / 2
A window matches when D_int <= TOL_INT*(n-1) and D_rc <= TOL_RC*(n-2).  The same scan is run on NULL surrogate corpora
(s03b_null.surrogate); a pattern's approximate matches are kept only when the surrogates give on average <= CHANCE hits.
Matches are merged into statements (GAP) and those overlapping an existing occurrence are dropped.
Input: a list of candidate ids (one per line) from a file; output: work/expansions.pkl {id: [occurrence dicts]}.
Run: discovery/.venv/bin/python -I discovery/tools/s07_expand.py <ids file>
"""
import os
import pickle
import sys

import numpy as np
from numba import njit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
import mine
import s03b_null
from common import WORK

TOL_INT = 0.15
TOL_RC = 0.25
CHANCE = 0.2
GAP = 4.0
SURROGATES = 3


@njit(cache=True)
def scan(semi, rc, seg, pat_i, pat_r, tol_i, tol_r):
    n = len(pat_i) + 1
    N = len(semi)
    out_s = []
    out_d = []
    for s in range(N - n + 1):
        if seg[s] != seg[s + n - 1]:
            continue
        d = 0.0
        for k in range(n - 1):
            x = abs(int(semi[s + k]) - int(pat_i[k]))
            d += 0.0 if x == 0 else (0.5 if x == 1 else 1.0)
            if d > tol_i:
                break
        if d > tol_i:
            continue
        r = 0.0
        for k in range(n - 2):
            x = abs(int(rc[s + 1 + k]) - int(pat_r[k]))
            r += min(x, 2) / 2.0
            if r > tol_r:
                break
        if r > tol_r:
            continue
        out_s.append(s)
        out_d.append(d + r)
    return out_s, out_d


def pattern_of(c, cand):
    w = cand["seed"]["stm"][0][0]
    n = cand["seed"]["n"]
    return c["semi"][w:w + n - 1].astype(np.int64), c["rc"][w + 1:w + n - 1].astype(np.int64), n


def hits(scanned, pattern):
    """Windows of corpus `scanned` that match `pattern` = (intervals, rhythm classes, n) taken from the REAL corpus."""
    pi, pr, n = pattern
    s, d = scan(scanned["semi"], scanned["rc"], scanned["seg"], pi, pr, TOL_INT * (n - 1), TOL_RC * (n - 2))
    return np.array(s, dtype=np.int64), np.array(d), n


def main(ids_file):
    ids = [int(x) for x in open(ids_file).read().split()]
    c = corpus.load()
    cands = {x["id"]: x for x in pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))}
    rng = np.random.default_rng(777)
    nulls = [s03b_null.surrogate(c, rng) for _ in range(SURROGATES)]
    result = {}
    for i in ids:
        x = cands[i]
        pat = pattern_of(c, x)
        s, d, n = hits(c, pat)
        chance = np.mean([len(hits(z, pat)[0]) for z in nulls])
        if chance > CHANCE:
            result[i] = dict(kept=False, chance=float(chance), hits=len(s), occ=[])
            continue
        known = [(o["act"], o["t0"] - 1.0, o["t1"] + 1.0) for o in x["fam"]["occ"]]
        order = np.argsort(c["t"][s]) if len(s) else s
        occ = []
        for j in sorted(range(len(s)), key=lambda j: (int(c["act"][s[j]]), float(c["t"][s[j]]))):
            w0, w1 = int(s[j]), int(s[j]) + n - 1
            act, t0, t1 = int(c["act"][w0]), float(c["t"][w0]), float(c["t"][w1])
            if any(a == act and t0 <= e and b <= t1 for a, b, e in known):
                continue
            if occ and occ[-1]["act"] == act and t0 <= occ[-1]["t1"] + GAP:
                occ[-1]["t1"] = max(occ[-1]["t1"], t1)
                occ[-1]["parts"].append((w0, w1, -1))
                occ[-1]["dist"] = min(occ[-1]["dist"], float(d[j]))
            else:
                occ.append(dict(act=act, t0=t0, t1=t1, parts=[(w0, w1, -1)], dist=float(d[j])))
        result[i] = dict(kept=True, chance=float(chance), hits=len(s), occ=occ)
    with open(os.path.join(WORK, "expansions.pkl"), "wb") as fh:
        pickle.dump(result, fh)
    tot = sum(len(v["occ"]) for v in result.values())
    print(f"{len(ids)} patterns; {sum(v['kept'] for v in result.values())} kept; {tot} new approximate occurrences")


if __name__ == "__main__":
    main(sys.argv[1])
