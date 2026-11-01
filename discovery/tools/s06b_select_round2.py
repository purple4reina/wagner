"""Step 6b. Choose the candidates for the second round of review.

Round 1 (batches 01-06) reviewed the pool of the first, stricter thresholds. After the null-model calibration the pool
grew (s05b_reduce.py). Round 2 reviews (a) the candidates added to the pool that are not already covered by an accepted
leitmotif (>= 75 % of their occurrences lie inside accepted occurrences, or their intervals repeat an accepted pattern),
and that have a contrasting rhythm (tier "motif": less than 85 % of the notes have the same duration; uniform-rhythm
patterns are figuration by rule, since the criteria ask for long and short notes), and (b) round 1's label-U candidates.
Needs: work/pool_v1.pkl (the pool of round 1, saved before s05b was relaxed), results/leitmotifs/*.json (round 1 build).
Result: decisions/round2_ids.txt (committed: it must be made while only batches 01-06 exist, so it is a decision file). Run: discovery/.venv/bin/python -I discovery/tools/s06b_select_round2.py
"""
import glob
import json
import os
import pickle
import sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
from common import ACTS, DECISIONS, RESULTS, WORK
from s07b_group import load_verdicts


def main():
    c = corpus.load()
    v1 = {x["id"] for x in pickle.load(open(os.path.join(WORK, "pool_v1.pkl"), "rb"))}
    pool = pickle.load(open(os.path.join(WORK, "pool.pkl"), "rb"))
    acc = [json.load(open(f)) for f in glob.glob(os.path.join(RESULTS, "leitmotifs", "*.json"))]
    by_act = {}
    for g in acc:
        for o in g["occurrences"]:
            by_act.setdefault(o["act"], []).append((o["pos0"] - 1, o["pos1"] + 1))
    free = []
    for x in pool:
        if x["id"] in v1 or x["tier"] != "motif":
            continue
        iv = []
        for o in x["fam"]["occ"]:
            w0, w1 = min(p[0] for p in o["parts"]), max(p[1] for p in o["parts"])
            iv.append((ACTS[int(c["act"][w0])], float(c["pos"][w0]), float(c["pos"][w1])))
        hit = sum(1 for a, p0, p1 in iv if any(s <= p1 and p0 <= e for s, e in by_act.get(a, ())))
        if hit / len(iv) >= 0.75:
            continue
        ints = [t - (9 if x["kind"] == "dint" else 15) for t in x["seed"]["tokens"][0]]
        if x["kind"] == "semi" and any(
                SequenceMatcher(None, ints, g["pattern_intervals"], autojunk=False).find_longest_match(
                    0, len(ints), 0, len(g["pattern_intervals"])).size >= 0.85 * len(ints) for g in acc):
            continue
        free.append(x["id"])
    unsure = sorted(i for i, v in load_verdicts().items() if v["label"] == "U")
    ids = free + unsure
    open(os.path.join(DECISIONS, "round2_ids.txt"), "w").write(" ".join(map(str, ids)) + "\n")
    print(f"round 2: {len(free)} new contrasting-rhythm candidates + {len(unsure)} unsure from round 1 = {len(ids)}")


if __name__ == "__main__":
    main()
