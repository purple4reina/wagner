"""Explore: print a random sample of candidates (tier motif) in dossier-lite form.
Run: discovery/.venv/bin/python -I discovery/explore/e05_sample_candidates.py <count> <seed> <min n> <max stepwise>
"""
import os, pickle, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import corpus, dossier
from common import WORK
count, seed, minn, maxstep = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
c = corpus.load()
cands = pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))
pool = [x for x in cands if x["tier"] == "motif" and x["f"]["n"] >= minn and x["f"]["stepwise"] <= maxstep]
print(len(pool), "in pool")
rng = np.random.default_rng(seed)
for i in rng.choice(len(pool), size=min(count, len(pool)), replace=False):
    x = pool[i]; f = x["f"]
    names, ioi = dossier.pattern_notes(c, x["seed"], x["seed"]["stm"][0][0])
    print(f"#{x['id']} {x['kind']} n={f['n']} ic={f['ic']:.0f} occ={f['n_occ']} sc={f['n_scenes']} ops={f['n_operas']} | {' '.join(names[:12])} | {' '.join(map(str, ioi[:11]))}")
    for o in x["fam"]["occ"][:3]:
        r = dossier.occurrence_row(c, o)
        print(f"     {r['act_short']} m{r['measure']} {r['streams'][0]} | {r['text'][:70]}")
