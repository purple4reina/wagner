"""Debug: why does the approximate scan find many hits in a surrogate corpus?"""
import os, pickle, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import corpus, s03b_null, s07_expand
from common import WORK
c = corpus.load()
cands = {x["id"]: x for x in pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))}
z = s03b_null.surrogate(c, np.random.default_rng(1))
x = cands[337]
pi, pr, n = s07_expand.pattern_of(c, x)
print("pattern ints", (pi - 15).tolist(), "rc", pr.tolist())
s, d, _ = s07_expand.hits(z, (pi, pr, n))
print("surrogate hits", len(s))
for w in s[:4]:
    print("  ", (z["semi"][w:w + n - 1].astype(int) - 15).tolist(), z["rc"][w + 1:w + n - 1].tolist())
print("surrogate semi token counts (value:count) top:", np.unique(z["semi"], return_counts=True)[1][:40])
print("real      semi token counts:", np.unique(c["semi"], return_counts=True)[1][:40])
print("surrogate rc counts", np.unique(z["rc"], return_counts=True), "real", np.unique(c["rc"], return_counts=True))
