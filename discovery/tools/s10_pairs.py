"""Step 10. Motifs heard twice exactly and again in varied form ("2 exact + 1 approximate").

The miner (s03) needs three exact statements. A motif that recurs twice unchanged and a third time with one note
or one rhythm changed also has three occurrences, so: take informative maximal repeats with exactly two statements
(n >= NMIN_PAIR, IC >= IC_PAIR), scan the whole score for approximate matches (s07_expand.scan: <= 15 % of intervals,
<= 25 % of rhythm classes differ), keep those with at least one extra statement, that give <= CHANCE hits in the surrogate
corpora, whose statements lie in >= 2 scenes, and that are not already inside an accepted leitmotif.
Result: work/pairs.pkl (candidate-like dicts with ids from PAIR_ID0 up) and a count.
Run: discovery/.venv/bin/python -I discovery/tools/s10_pairs.py [--null]
"""
import glob
import json
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
import s03_seeds
import s03b_null
import s07_expand
from common import ACTS, RESULTS, WORK

NMIN_PAIR = 8
IC_PAIR = 26.0
PAIR_ID0 = 100000
GAP = 4.0
SLACK = 1.0


def find_pairs(c, nulls, by_act):
    """The procedure on corpus `c` (real or surrogate); `nulls` are surrogate corpora for the chance guard."""
    seeds = s03_seeds.mine_seeds(c, "semi", IC_PAIR, verbose=False, min_stmt=2, min_scenes=1, nmin=NMIN_PAIR)
    seeds = [x for x in seeds if len(x["stm"]) == 2]
    out, stats = [], dict(seeds=len(seeds), no_extra=0, chance=0, one_scene=0, covered=0)
    for k, sd in enumerate(seeds):
        w = sd["stm"][0][0]
        n = sd["n"]
        pat = (c["semi"][w:w + n - 1].astype(np.int64), c["rc"][w + 1:w + n - 1].astype(np.int64), n)
        s, d, _ = s07_expand.hits(c, pat)
        known = [(int(c["act"][a]), float(c["t"][a]) - SLACK, float(c["t"][b]) + SLACK) for a, b in sd["stm"]]
        occ = [dict(act=int(c["act"][a]), t0=float(c["t"][a]), t1=float(c["t"][b]), parts=[(a, b, k)], dist=0.0, exact=True)
               for a, b in sd["stm"]]
        extra = []
        for j in sorted(range(len(s)), key=lambda j: (int(c["act"][s[j]]), float(c["t"][s[j]]))):
            w0, w1 = int(s[j]), int(s[j]) + n - 1
            act, t0, t1 = int(c["act"][w0]), float(c["t"][w0]), float(c["t"][w1])
            if any(a == act and b <= t1 and t0 <= e for a, b, e in known):
                continue
            if extra and extra[-1]["act"] == act and t0 <= extra[-1]["t1"] + GAP:
                extra[-1]["t1"] = max(extra[-1]["t1"], t1)
                continue
            extra.append(dict(act=act, t0=t0, t1=t1, parts=[(w0, w1, -1)], dist=float(d[j]), exact=False))
        if not extra:
            stats["no_extra"] += 1
            continue
        if np.mean([len(s07_expand.hits(z, pat)[0]) for z in nulls]) > s07_expand.CHANCE:
            stats["chance"] += 1
            continue
        allocc = sorted(occ + extra, key=lambda o: (o["act"], o["t0"]))
        scenes = {int(c["scene"][o["parts"][0][0]]) for o in allocc}
        if len(scenes) < 2:
            stats["one_scene"] += 1
            continue
        hit = sum(1 for o in allocc if any(a <= o["t1"] and o["t0"] <= e for a, e in by_act.get(ACTS[o["act"]], ())))
        if hit / len(allocc) >= 0.75:
            stats["covered"] += 1
            continue
        out.append(dict(id=PAIR_ID0 + len(out), kind="semi", seed=sd, tier="pair",
                        fam=dict(occ=allocc, n_scenes=len(scenes), n_acts=len({o["act"] for o in allocc}),
                                 n_operas=len({ACTS[o["act"]][6] for o in allocc}), members=[], rep=k),
                        f=dict(n=n, ic=sd["ic"], n_occ=len(allocc), n_scenes=len(scenes),
                               n_operas=len({ACTS[o["act"]][6] for o in allocc}), exact=2)))
    return out, stats


def main():
    c = corpus.load()
    acc = [json.load(open(f)) for f in glob.glob(os.path.join(RESULTS, "leitmotifs", "*.json"))]
    by_act = {}
    for g in acc:
        for o in g["occurrences"]:
            by_act.setdefault(o["act"], []).append((o["pos0"] - SLACK, o["pos1"] + SLACK))
    rng = np.random.default_rng(4242)
    if "--null" in sys.argv:  # the same procedure on surrogate music: how many "pair + approximate" motifs are chance?
        for r in range(2):
            z = s03b_null.surrogate(c, rng)
            out, stats = find_pairs(z, [s03b_null.surrogate(c, rng) for _ in range(s07_expand.SURROGATES)], {})
            print("surrogate", r, stats, "->", len(out))
        return
    out, stats = find_pairs(c, [s03b_null.surrogate(c, rng) for _ in range(s07_expand.SURROGATES)], by_act)
    pickle.dump(out, open(os.path.join(WORK, "pairs.pkl"), "wb"))
    print(stats, "->", len(out), "new pair+approximate candidates")


if __name__ == "__main__":
    main()
