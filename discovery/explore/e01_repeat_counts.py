"""Explore: how many exact repeated windows are there, by length n and information content (IC)?

Counts window groups (same interval+rhythm key) that occur >= 3 times in >= 2 scenes, ignoring deduplication
(raw counts, so several streams and neighbouring windows inflate them). Used to choose the thresholds in s03.
Run: discovery/.venv/bin/python -I discovery/explore/e01_repeat_counts.py [semi|dint]
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
size = 32
valid_i = tok != 31
bi = mine.surprisal(tok, valid_i, size)
br = mine.surprisal(c["rc"], c["rc"] != 5, 6)
H = mine.Hasher(tok, c["rc"], c["seg"])
print(f"kind={kind}  bits/interval mean={bi[valid_i].mean():.2f}  bits/rhythm mean={br[c['rc']!=5].mean():.2f}")
print("n  windows  groups>=3&>=2scenes  by IC>=[20,30,40,50]")
for n in range(5, 21):
    s = H.starts(n)
    k = H.keys(n, s)
    ic = mine.window_ic(bi, br, s, n)
    u, inv, cnt = np.unique(k, return_inverse=True, return_counts=True)
    sc = c["scene"][s]
    smin = np.full(len(u), 10**6)
    smax = np.full(len(u), -1)
    np.minimum.at(smin, inv, sc)
    np.maximum.at(smax, inv, sc)
    gic = np.zeros(len(u))
    gic[inv] = ic
    good = (cnt >= 3) & (smax > smin)
    row = [int(good.sum())] + [int((good & (gic >= t)).sum()) for t in (20, 30, 40, 50)]
    print(n, len(s), *row)
