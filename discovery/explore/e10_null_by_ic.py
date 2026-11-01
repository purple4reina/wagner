"""Explore: real vs null seed counts by information-content bin, for short patterns (n = 5..9)."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import corpus, s03_seeds, s03b_null
c = corpus.load()
real = s03_seeds.mine_seeds(c, "semi", 20.0, verbose=False)
rng = np.random.default_rng(99)
nulls = [s03_seeds.mine_seeds(s03b_null.surrogate(c, rng), "semi", 20.0, verbose=False) for _ in range(4)]
bins = [(20, 22), (22, 24), (24, 26), (26, 28), (28, 30), (30, 99)]
print("n  bin      real  null(mean of 4)   [seeds with >= 4 statements: real null]")
for n in range(5, 10):
    for lo, hi in bins:
        r = [x for x in real if x["n"] == n and lo <= x["ic"] < hi]
        z = np.mean([sum(1 for x in nl if x["n"] == n and lo <= x["ic"] < hi) for nl in nulls])
        r4 = sum(1 for x in r if len(x["stm"]) >= 4)
        z4 = np.mean([sum(1 for x in nl if x["n"] == n and lo <= x["ic"] < hi and len(x["stm"]) >= 4) for nl in nulls])
        if len(r) or z:
            print(f"{n}  {lo:>2}-{hi:<3} {len(r):>5}  {z:>6.1f}   [{r4} {z4:.1f}]")
