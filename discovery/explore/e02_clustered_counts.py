"""Explore: exact repeated windows after merging windows that overlap or lie within 4 quarter notes (one "statement").

Counts groups with >= 3 statements in >= 2 scenes, by length n and information content (IC).
Run: discovery/.venv/bin/python -I discovery/explore/e02_clustered_counts.py [semi|dint]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import corpus
import mine

kind = sys.argv[1] if len(sys.argv) > 1 else "semi"
c = corpus.load()
tok = c[kind]
bi = mine.markov_bits(tok, c["seg"], 32, skip=31)
br = mine.markov_bits(c["rc"], c["seg"], 6, skip=5)
H = mine.Hasher(tok, c["rc"], c["seg"])
print("n  groups(>=3 stmts, >=2 scenes) by IC2>=[0,15,20,25,30,35]")
for n in range(5, 21):
    s = H.starts(n)
    k = H.keys(n, s)
    ic = mine.window_ic2(bi, br, s, n)
    order, cl, grp = mine.group_clusters(k, c["act"][s], c["t"][s], c["t"][s + n - 1])
    so = s[order]
    ng = grp[-1] + 1
    # statements per group: clusters are numbered globally, so count distinct cluster ids per group
    first = np.ones(len(cl), bool)
    first[1:] = cl[1:] != cl[:-1]
    nst = np.bincount(grp[first], minlength=ng)
    scn = c["scene"][so]
    smin = np.full(ng, 10**6); smax = np.full(ng, -1)
    np.minimum.at(smin, grp[first], scn[first]); np.maximum.at(smax, grp[first], scn[first])
    gic = np.zeros(ng); gic[grp] = ic[order]
    good = (nst >= 3) & (smax > smin)
    print(n, *[int((good & (gic >= t)).sum()) for t in (0, 15, 20, 25, 30, 35)])
