"""Step 3b. Null model: how many "seeds" would the miner find in music with NO recurring leitmotifs?

We sample surrogate corpora from the order-2 Markov model fitted to the real corpus (interval tokens and rhythm
classes separately), keeping the real layout (segments, times, scenes), and run the same seed miner on them.
The Markov model contains the local habits of the music (scales, arpeggios, tremolos) but no long-range recurrence,
so the number of seeds found at each length n is the number expected by chance; the surplus in the real corpus is
the signal. (The model is fitted on data that contains real motifs, so the surrogate is, if anything, too generous.)
Writes discovery/results/null_model.tsv. Run: discovery/.venv/bin/python -I discovery/tools/s03b_null.py [repeats] [IC_MIN] [kind]
"""
import os
import sys

import numpy as np
from numba import njit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
import mine
import s03_seeds
from common import RESULTS


@njit(cache=True)
def _gen(cdf0, cdf1, cdf2, lo, hi, rnd, out):
    """Fill out[lo[k]..hi[k]] of every segment k from the order-2 model (cdf* are cumulative probabilities)."""
    for k in range(len(lo)):
        for i in range(lo[k], hi[k] + 1):
            r = rnd[i]
            if i == lo[k]:
                cdf = cdf0
            elif i == lo[k] + 1:
                cdf = cdf1[out[i - 1]]
            else:
                cdf = cdf2[out[i - 2], out[i - 1]]
            j = 0
            while j < len(cdf) - 1 and cdf[j] < r:
                j += 1
            out[i] = j


def surrogate(c, rng):
    seg = c["seg"]
    N = len(seg)
    starts = np.concatenate([[0], np.nonzero(np.diff(seg))[0] + 1])
    ends = np.concatenate([starts[1:] - 1, [N - 1]])  # last index of each segment
    out = {k: v for k, v in c.items()}
    # intervals: positions start .. end-1
    P0, P1, P2, _, _ = mine.markov_tables(c["semi"], seg, 32, skip=31)
    semi = np.full(N, 31, dtype=np.int64)
    ok = ends > starts
    _gen(np.cumsum(P0), np.cumsum(P1, axis=1), np.cumsum(P2, axis=2), starts[ok], ends[ok] - 1, rng.random(N), semi)
    # rhythm classes: positions start+1 .. end-1
    Q0, Q1, Q2, _, _ = mine.markov_tables(c["rc"], seg, 6, skip=5)
    rc = np.full(N, 5, dtype=np.int64)
    ok = ends - starts >= 2
    _gen(np.cumsum(Q0), np.cumsum(Q1, axis=1), np.cumsum(Q2, axis=2), starts[ok] + 1, ends[ok] - 1, rng.random(N), rc)
    semi[semi == 31] = 31
    out["semi"] = semi.astype(np.int8)
    out["rc"] = rc.astype(np.int8)
    step = np.where(semi == 31, 0, semi - 15)
    cum = np.cumsum(np.concatenate([[0], step[:-1]]))
    base = cum[np.repeat(starts, ends - starts + 1)]
    out["pitch"] = (60 + cum - base).astype(np.int32)  # the exact register does not matter, only the distinct count
    return out


def main(repeats=3, ic_min=s03_seeds.IC_MIN_DEFAULT, kind="semi"):
    c = corpus.load()
    real = s03_seeds.mine_seeds(c, kind, ic_min, verbose=False)
    rng = np.random.default_rng(12345)
    nulls = [s03_seeds.mine_seeds(surrogate(c, rng), kind, ic_min, verbose=False) for _ in range(repeats)]
    os.makedirs(RESULTS, exist_ok=True)
    lines = ["n\treal_seeds\tnull_mean\tnull_max\tfraction_real_that_is_chance_at_most\treal_ic>=30\tnull_ic>=30\treal_occ>=4\tnull_occ>=4"]
    for n in range(s03_seeds.NMIN, s03_seeds.NMAX + 1):
        r = [x for x in real if x["n"] == n]
        z = [[x for x in nl if x["n"] == n] for nl in nulls]
        zc = np.array([len(a) for a in z])
        frac = min(1.0, zc.mean() / max(len(r), 1))
        lines.append("\t".join(str(v) for v in (
            n, len(r), f"{zc.mean():.1f}", zc.max(), f"{frac:.2f}",
            sum(x["ic"] >= 30 for x in r), f"{np.mean([sum(x['ic'] >= 30 for x in a) for a in z]):.1f}",
            sum(len(x["stm"]) >= 4 for x in r), f"{np.mean([sum(len(x['stm']) >= 4 for x in a) for a in z]):.1f}")))
    with open(os.path.join(RESULTS, "null_model.tsv" if kind == "semi" else f"null_model_{kind}.tsv"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:26]))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3, float(sys.argv[2]) if len(sys.argv) > 2 else s03_seeds.IC_MIN_DEFAULT,
         sys.argv[3] if len(sys.argv) > 3 else "semi")
