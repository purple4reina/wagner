"""Explore: print a few exact-repeat groups of length n so they can be judged by eye.
Run: discovery/.venv/bin/python -I discovery/explore/e03_peek_groups.py <semi|dint> <n> <how many> [seed] [min IC2]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import corpus
import mine
from common import ACTS, SHORT

kind, n, howmany = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 0
minic = float(sys.argv[5]) if len(sys.argv) > 5 else 0
c = corpus.load()
tok = c[kind]
bi = mine.markov_bits(tok, c["seg"], 32, skip=31)
br = mine.markov_bits(c["rc"], c["seg"], 6, skip=5)
H = mine.Hasher(tok, c["rc"], c["seg"])
s = H.starts(n)
k = H.keys(n, s)
ic = mine.window_ic2(bi, br, s, n)
order, cl, grp = mine.group_clusters(k, c["act"][s], c["t"][s], c["t"][s + n - 1])
so = s[order]
ng = grp[-1] + 1
first = np.ones(len(cl), bool); first[1:] = cl[1:] != cl[:-1]
nst = np.bincount(grp[first], minlength=ng)
scn = c["scene"][so]
smin = np.full(ng, 10**6); smax = np.full(ng, -1)
np.minimum.at(smin, grp[first], scn[first]); np.maximum.at(smax, grp[first], scn[first])
gic = np.zeros(ng); gic[grp] = ic[order]
good = np.nonzero((nst >= 3) & (smax > smin) & (gic >= minic))[0]
rng = np.random.default_rng(seed)
pick = rng.choice(good, size=min(howmany, len(good)), replace=False)
starts_of = np.concatenate([[0], np.nonzero(np.diff(grp))[0] + 1, [len(grp)]])
for g in pick:
    idx = np.arange(starts_of[g], starts_of[g + 1])
    f = so[idx[first[idx]]]
    w = f[0]
    ints = [int(x) - (15 if kind == "semi" else 9) for x in tok[w:w + n - 1]]
    rh = [round(float(x), 2) for x in c["ioi"][w:w + n - 1]]
    locs = ", ".join(f"{SHORT[ACTS[c['act'][x]]]}:{int(c['measure'][x])}{c['stream_name_of_note'][x]}" for x in f[:8])
    print(f"n={n} stmts={nst[g]} scenes={len(set(c['scene'][f].tolist()))} IC={ic[order][idx[0]]:.0f}\n  int={ints}\n  ioi={rh}\n  at {locs}")
