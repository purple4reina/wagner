"""Explore: how many of the tier-2 candidates are already covered by accepted leitmotifs (so need no review)?"""
import json, glob, os, pickle, sys
from difflib import SequenceMatcher
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from common import WORK, RESULTS
v1 = {x["id"] for x in pickle.load(open(os.path.join(WORK, "pool_v1.pkl"), "rb"))}
pool = pickle.load(open(os.path.join(WORK, "pool.pkl"), "rb"))
new = [x for x in pool if x["id"] not in v1]
acc = [json.load(open(f)) for f in glob.glob(os.path.join(RESULTS, "leitmotifs", "*.json"))]
by_act = {}
for g in acc:
    for o in g["occurrences"]:
        by_act.setdefault(o["act"], []).append((o["pos0"] - 1, o["pos1"] + 1))
import corpus
c = corpus.load()
def pos_iv(x):
    out = []
    for o in x["fam"]["occ"]:
        w0 = min(p[0] for p in o["parts"]); w1 = max(p[1] for p in o["parts"])
        out.append((__import__("common").ACTS[int(c["act"][w0])], float(c["pos"][w0]), float(c["pos"][w1])))
    return out
covered_share = covered_seq = 0
free = []
for x in new:
    iv = pos_iv(x)
    hit = sum(1 for a, p0, p1 in iv if any(s <= p1 and p0 <= e for s, e in by_act.get(a, ())))
    sh = hit / len(iv)
    ints = [t - (9 if x["kind"] == "dint" else 15) for t in x["seed"]["tokens"][0]]
    q = 0.0
    if x["kind"] == "semi":
        for g in acc:
            m = SequenceMatcher(None, ints, g["pattern_intervals"], autojunk=False).find_longest_match(0, len(ints), 0, len(g["pattern_intervals"]))
            q = max(q, m.size / len(ints))
            if q >= 0.85: break
    if sh >= 0.75: covered_share += 1
    elif q >= 0.85: covered_seq += 1
    else: free.append(x["id"])
print(len(new), "new;", covered_share, "inside accepted occurrences;", covered_seq, "repeat an accepted interval run;", len(free), "free")
open(os.path.join(WORK, "tier2_free_ids.txt"), "w").write(" ".join(map(str, free)))
