"""Step 6c. Choose the candidates for review round 3 (the correction round).

Rounds 1 and 2 let rhythm variety decide things it must not decide: candidates with uniform durations were tagged
"figuration" for the reviewers, skipped in round 2, and removed from the results; a clause dropped stepwise patterns
with little duration contrast; and the reviewers' F labels were predicted by uniformity (AUC 0.96). The user's rhythm
criterion is that occurrences match each other in rhythm, not that a motif's durations vary.
Round 3 therefore re-reviews, blind to rhythm and under one rubric (exclude only stock figures), every candidate of the
pool that is not already accepted: those labelled F, G or U in rounds 1-2, and those never reviewed (uniform-rhythm ones,
and the ones the contrast clause had removed). Candidates already inside accepted occurrences (>= 75 % of their
occurrences) or repeating an accepted interval run are not reviewed: they would only merge into an accepted leitmotif.
Needs the round 1-2 build in results/leitmotifs/*.json. Result: decisions/round3_ids.txt (a decision file: it is made once).
One-off: it reads the round 1-2 build and the verdicts of that moment, so it is NOT part of run_all.sh and gives a different
answer if rerun later; its output decisions/round3_ids.txt is the record.
Run: discovery/.venv/bin/python -I discovery/tools/s06c_select_round3.py
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


def accepted_index():
    """Occurrence intervals of the accepted leitmotifs of the current build, by act, and their patterns."""
    acc = [json.load(open(f)) for f in glob.glob(os.path.join(RESULTS, "leitmotifs", "*.json"))]
    by_act = {}
    for g in acc:
        for o in g["occurrences"]:
            by_act.setdefault(o["act"], []).append((o["pos0"] - 1, o["pos1"] + 1))
    return acc, by_act


def is_covered(c, x, acc, by_act):
    """True if >= 75 % of the candidate's occurrences lie inside accepted occurrences, or its intervals repeat an
    accepted pattern's interval run (>= 85 % of its length): it would only merge into an accepted leitmotif."""
    iv = []
    for o in x["fam"]["occ"]:
        w0, w1 = min(p[0] for p in o["parts"]), max(p[1] for p in o["parts"])
        iv.append((ACTS[int(c["act"][w0])], float(c["pos"][w0]), float(c["pos"][w1])))
    hit = sum(1 for a, p0, p1 in iv if any(s <= p1 and p0 <= e for s, e in by_act.get(a, ())))
    if hit / len(iv) >= 0.75:
        return True
    if x["kind"].startswith("semi"):
        ints = [t - 15 for t in x["seed"]["tokens"][0]]
        return any(SequenceMatcher(None, ints, g["pattern_intervals"], autojunk=False).find_longest_match(
            0, len(ints), 0, len(g["pattern_intervals"])).size >= 0.85 * len(ints) for g in acc)
    return False


def main():
    c = corpus.load()
    pool = pickle.load(open(os.path.join(WORK, "pool.pkl"), "rb"))
    verdicts = load_verdicts(rules=False)
    acc, by_act = accepted_index()
    ids, why = [], {"F": 0, "G": 0, "U": 0, "unreviewed": 0, "covered": 0}
    for x in pool:
        lab = verdicts.get(x["id"], {}).get("label", "-")
        if lab == "M":
            continue
        covered = is_covered(c, x, acc, by_act)
        if covered:
            why["covered"] += 1
            continue
        ids.append(x["id"])
        why[lab if lab in "FGU" and lab != "-" else "unreviewed"] += 1
    open(os.path.join(DECISIONS, "round3_ids.txt"), "w").write(" ".join(map(str, ids)) + "\n")
    print(f"round 3: {len(ids)} candidates to review; by earlier status {why}")


if __name__ == "__main__":
    main()
