"""Audit: is the IC threshold equally safe for patterns with uniform and with varied rhythm?
Seeds (IC >= 20, >= 3 statements in >= 2 scenes) in the score vs 4 surrogate corpora, split by whether >= 85 % of the
rhythm classes say "same duration as the note before" (rc == 2) and by IC bin.  A bin where the surrogates produce as many
seeds as the score would need a higher threshold FOR THAT KIND of pattern -- a statistical, not a musical, reason.
Run: discovery/.venv/bin/python -I discovery/explore/e18_null_by_rhythm_uniformity.py
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import corpus, s03_seeds, s03b_null
c = corpus.load()
def split(seeds):
    out = {}
    for x in seeds:
        rc = x["tokens"][1]
        uni = (np.mean(np.array(rc) == 2) >= 0.85) if rc else False
        b = "20-22" if x["ic"] < 22 else "22-24" if x["ic"] < 24 else "24-26" if x["ic"] < 26 else "26-30" if x["ic"] < 30 else "30+"
        k = ("uniform" if uni else "varied", b)
        out[k] = out.get(k, 0) + 1
    return out
real = split(s03_seeds.mine_seeds(c, "semi", 20.0, verbose=False))
rng = np.random.default_rng(31)
nulls = [split(s03_seeds.mine_seeds(s03b_null.surrogate(c, rng), "semi", 20.0, verbose=False)) for _ in range(4)]
print("rhythm   IC      real   null(mean of 4)")
for u in ("uniform", "varied"):
    for b in ("20-22", "22-24", "24-26", "26-30", "30+"):
        print(f"{u:8s} {b:6s} {real.get((u, b), 0):5d}  {np.mean([n.get((u, b), 0) for n in nulls]):7.1f}")
