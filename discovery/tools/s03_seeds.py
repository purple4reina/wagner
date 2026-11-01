"""Step 3. Mine "seeds": maximal exact repeats of (interval, rhythm-class) windows across the whole cycle.

A seed is a pattern of n notes (5 <= n <= NMAX) such that
  * it occurs in >= 3 statements, in >= 2 different scenes (statement = windows that overlap or start within
    GAP quarter notes of each other, in the same act; the same melody seen in several streams is one statement);
  * it is maximal: no longer pattern has the same occurrences (we keep the longest);
  * its information content under the order-2 Markov model of the corpus is >= IC_MIN bits, which removes trills,
    scale runs, arpeggio cells and other texture that is predictable from its own first notes.
`kind` chooses the interval alphabet: "semi" (semitones, exact), "dint" (diatonic steps, so that a major and a minor
third are the same; finds mode variants) or "semi_nr" (semitones, rhythm ignored: finds motifs whose rhythm changes). Result: discovery/work/seeds_<kind>.pkl, a list of dicts.
Run: discovery/.venv/bin/python -I discovery/tools/s03_seeds.py <semi|dint> [IC_MIN]
"""
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
import mine
from common import WORK

NMIN, NMAX = 5, 48
GAP = 4.0  # quarter notes: windows closer than this are one statement
IC_MIN_DEFAULT = 22.0
MIN_CELL = 5  # a window that repeats a cell of fewer notes than this (a trill, a tremolo, ...) is not a melody
MIN_PITCHES = 3  # distinct pitches in the window


def too_simple(ints, pitches, kind_offset=None):
    """True if the window is (almost) periodic with a period shorter than MIN_CELL notes, or has < MIN_PITCHES pitches."""
    if len(set(pitches)) < MIN_PITCHES:
        return True
    a = np.array(ints)
    if kind_offset is not None and len(a) > 2:
        d = a - kind_offset
        if np.mean(d[:-1] == -d[1:]) >= 0.6:  # up-and-back by the same amount: an oscillation
            return True
    for p in range(1, MIN_CELL):
        if len(a) >= 2 * p and np.mean(a[:-p] == a[p:]) >= 0.85:
            return True
    return False


def mine_seeds(c, kind, ic_min, verbose=True, min_stmt=3, min_scenes=2, nmin=NMIN):
    """Seeds of corpus `c` (the real one, or a surrogate from s03b_null.py)."""
    use_rhythm = not kind.endswith("_nr")
    tok = c["dint" if kind == "dint" else "semi"]
    N = len(tok)
    skip = 31
    bi = mine.markov_bits(tok, c["seg"], 32, skip=skip)
    br = mine.markov_bits(c["rc"], c["seg"], 6, skip=5)
    if not use_rhythm:
        br = tuple(np.zeros_like(b) for b in br)
    H = mine.Hasher(tok, c["rc"], c["seg"])
    seeds = []
    next_gsz = None  # group size of the window starting at each index, for n+1
    for n in range(NMAX, nmin - 1, -1):
        s = H.starts(n)
        if len(s) == 0:
            next_gsz = np.zeros(N + 1, dtype=np.int64)
            continue
        k = H.keys(n, s, use_rhythm)
        u, inv, cnt = np.unique(k, return_inverse=True, return_counts=True)
        gsz = np.zeros(N + 2, dtype=np.int64)
        gsz[s] = cnt[inv]
        ic = mine.window_ic2(bi, br, s, n)
        t0, t1 = c["t"][s], c["t"][s + n - 1]
        cand = cnt[inv] >= min_stmt
        if next_gsz is not None:
            right = next_gsz[s] == cnt[inv]
            left = np.zeros(len(s), bool)
            sl = s - 1
            okl = sl >= 0
            left[okl] = next_gsz[sl[okl]] == cnt[inv][okl]
            cand &= ~(right | left)
        cand &= ic >= ic_min
        if cand.any():
            ci = np.nonzero(cand)[0]
            order, cl, grp = mine.group_clusters(k[ci], c["act"][s[ci]], t0[ci], t1[ci], GAP)
            so = s[ci][order]
            icc = ic[ci][order]
            first = np.ones(len(cl), bool)
            first[1:] = cl[1:] != cl[:-1]
            gb = np.concatenate([[0], np.nonzero(np.diff(grp))[0] + 1, [len(grp)]])
            for g in range(len(gb) - 1):
                a, b = gb[g], gb[g + 1]
                f = np.nonzero(first[a:b])[0] + a
                if len(f) < min_stmt:
                    continue
                if len(set(c["scene"][so[f]].tolist())) < min_scenes:
                    continue
                w = so[a]
                if too_simple(tok[w:w + n - 1].tolist(), c["pitch"][w:w + n].tolist(), 9 if kind == "dint" else 15):
                    continue
                ends = np.concatenate([f[1:], [b]])
                stm = []
                for fi, ei in zip(f, ends):
                    w0 = so[fi]
                    w1 = so[ei - 1] + n - 1  # last note of the last window of this statement
                    stm.append((int(w0), int(w1)))
                seeds.append(dict(kind=kind, n=n, ic=float(icc[a]), nwin=int(b - a), stm=stm,
                                  tokens=(tok[so[a]:so[a] + n - 1].tolist(), c["rc"][so[a] + 1:so[a] + n - 1].tolist())))
        next_gsz = gsz
        if verbose:
            print(f"n={n}: {sum(1 for x in seeds if x['n'] == n)} seeds", flush=True)
    seeds.sort(key=lambda d: (-d["n"], -d["ic"]))
    return seeds


def main(kind, ic_min):
    seeds = mine_seeds(corpus.load(), kind, ic_min)
    with open(os.path.join(WORK, f"seeds_{kind}.pkl"), "wb") as f:
        pickle.dump(seeds, f)
    print(len(seeds), "seeds saved")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "semi", float(sys.argv[2]) if len(sys.argv) > 2 else IC_MIN_DEFAULT)
