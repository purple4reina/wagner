"""Step 6d. Accept by rule the candidates that the pitch-variety rules had kept out of review.

The user's criterion is "at least 5 notes, not necessarily different pitches", so a pattern is not rejected for having few
distinct pitches, a short repeated cell, or an oscillation. Two groups of candidates were affected and no reviewer has seen
them: (a) the formerly pitch-filtered families that s05 appended (kinds semi_simple / dint_simple, ids from 2127) and (b)
older candidates that the pool dropped for having < 4 pitches at n >= 7. Every pool candidate that has no verdict and is not
already covered by an accepted leitmotif (see s06c.is_covered) is accepted: label M, theme "(rule)". They are described, not
judged: s08 puts patterns with low pitch variety in their own INDEX section, and nothing is excluded.
One-off like s06c (it reads the build that existed before this step); the output decisions/rule_pitch_variety.tsv is the record.
Run: discovery/.venv/bin/python -I discovery/tools/s06d_accept_pitch_variety.py
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
from common import DECISIONS, WORK
from s06c_select_round3 import accepted_index, is_covered
from s07b_group import load_verdicts


def main():
    c = corpus.load()
    pool = pickle.load(open(os.path.join(WORK, "pool.pkl"), "rb"))
    verdicts = load_verdicts(rules=False)
    acc, by_act = accepted_index()
    rows, covered = [], 0
    for x in pool:
        if x["id"] in verdicts:
            continue
        if is_covered(c, x, acc, by_act):
            covered += 1
            continue
        rows.append(x["id"])
    with open(os.path.join(DECISIONS, "rule_pitch_variety.tsv"), "w", encoding="utf-8") as fh:
        fh.write("id\tlabel\ttheme\tsame_as\n")
        for i in rows:
            fh.write(f"{i}\tM\t(accepted by rule: pitch variety is not a criterion)\t-\n")
    print(f"{len(rows)} candidates accepted by rule ({covered} unreviewed ones were already covered by accepted leitmotifs)")


if __name__ == "__main__":
    main()
