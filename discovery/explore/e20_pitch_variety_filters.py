"""Audit: how much do the pitch-variety filters of s03_seeds.too_simple remove (>= 3 distinct pitches; no near-periodic cell
shorter than 5 notes; no oscillation)?  The user said the 5 notes need not have different pitches, so these are assumptions
too (about pitch, not rhythm).  Counts seeds that pass the IC/statement thresholds with and without the filter and how many
of the extra ones lie where no existing candidate is.
Run: discovery/.venv/bin/python -I discovery/explore/e20_pitch_variety_filters.py
"""
import collections, os, pickle, sys
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(root, "tools"))
import corpus, s03_seeds
from common import WORK
c = corpus.load()
with_f = s03_seeds.mine_seeds(c, "semi", 22.0, verbose=False)
orig = s03_seeds.too_simple
s03_seeds.too_simple = lambda *a, **k: False
without = s03_seeds.mine_seeds(c, "semi", 22.0, verbose=False)
s03_seeds.too_simple = orig
key = lambda x: (x["n"], tuple(x["tokens"][0]), tuple(x["tokens"][1]))
have = {key(x) for x in with_f}
extra = [x for x in without if key(x) not in have]
ok = lambda x: x["ic"] >= 24 or (x["ic"] >= 22 and len(x["stm"]) >= 4)
extra = [x for x in extra if ok(x)]
cands = pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))
by_act = collections.defaultdict(list)
for x in cands:
    for o in x["fam"]["occ"]:
        by_act[o["act"]].append((o["t0"] - 1, o["t1"] + 1))
new = 0
for x in extra:
    iv = [(int(c["act"][a]), float(c["t"][a]), float(c["t"][b])) for a, b in x["stm"]]
    hit = sum(1 for act, t0, t1 in iv if any(s <= t1 and t0 <= e for s, e in by_act[act]))
    new += hit / len(iv) < 0.5
print(len(with_f), "seeds with the filter;", len(without), "without;", len(extra), "extra seeds above the thresholds;",
      new, "of them mostly where no existing candidate is")
print("extra by n:", sorted(collections.Counter(min(x['n'], 14) for x in extra).items()))
