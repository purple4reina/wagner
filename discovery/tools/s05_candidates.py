"""Step 5. Unify the families of both interval alphabets into candidates and compute features for triage.

* A diatonic family is dropped when a semitone family already covers it (>= LINK of its occurrences overlap one of the
  semitone family's); otherwise it is added as a candidate (a mode variant or a motif the semitone alphabet split).
* Features of the representative occurrence: n notes, IC bits, rhythm uniformity (share of the most common duration),
  duration contrast, stepwise share (|interval| <= 2 semitones), and of the family: occurrences, scenes, acts,
  operas, distinct "passages" (occurrences more than PASSAGE quarter notes apart), streams.
* The rhythm features (uniform, contrast, median_ioi) are DESCRIPTIVE only. No selection step may use them: the user's
  rhythm criterion is that occurrences of a match have similar rhythm, not that a motif's own durations must vary
  (an earlier version tiered candidates by uniformity; that was a mistake, see METHODOLOGY section 9).
Result: discovery/work/candidates.pkl and candidates.tsv.
Run: discovery/.venv/bin/python -I discovery/tools/s05_candidates.py
"""
import os
import pickle
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
from common import ACTS, OPERA, SHORT, WORK

PASSAGE = 16.0
LINK = 0.6
SLACK = 1.0


def occ_intervals(fm):
    return sorted((o["act"], o["t0"], o["t1"]) for o in fm["occ"])


def covered_fraction(a, b):
    """Fraction of the intervals of `a` that overlap (within SLACK) some interval of `b`."""
    by_act = {}
    for act, t0, t1 in b:
        by_act.setdefault(act, []).append((t0 - SLACK, t1 + SLACK))
    hit = 0
    for act, t0, t1 in a:
        if any(s <= t1 and t0 <= e for s, e in by_act.get(act, ())):
            hit += 1
    return hit / len(a)


def features(c, seed, fm, kind):
    w = seed["stm"][0][0]
    n = seed["n"]
    ioi = c["ioi"][w:w + n - 1]
    q = np.round(ioi * 24) / 24  # triplet-safe quantisation
    modal = Counter(q.tolist()).most_common(1)[0][1] / len(q)
    ints = np.abs(c["pitch"][w + 1:w + n] - c["pitch"][w:w + n - 1])
    streams = Counter(s for o in fm["occ"] for s in {str(c["stream_name_of_note"][p[0]]) for p in o["parts"]})
    ts = sorted((o["act"], o["t0"]) for o in fm["occ"])
    passages = 1 + sum(1 for (a1, t1), (a2, t2) in zip(ts, ts[1:]) if a1 != a2 or t2 - t1 > PASSAGE)
    return dict(
        n=n, ic=seed["ic"], uniform=float(modal), contrast=float(q.max() / max(q.min(), 1e-6)),
        median_ioi=float(np.median(ioi)), stepwise=float(np.mean(ints <= 2)),
        pitches=int(len(set(c["pitch"][w:w + n].tolist()))), n_occ=len(fm["occ"]), passages=passages,
        n_scenes=fm["n_scenes"], n_acts=fm["n_acts"], n_operas=fm["n_operas"],
        top_stream_share=float(sum(v for k, v in streams.items() if k in ("T1", "L111")) / max(sum(streams.values()), 1)),
    )


def main():
    c = corpus.load()
    seeds = {k: pickle.load(open(os.path.join(WORK, f"seeds_{k}.pkl"), "rb")) for k in ("semi", "dint")}
    fams = {k: pickle.load(open(os.path.join(WORK, f"families_{k}.pkl"), "rb")) for k in ("semi", "dint")}
    cands = []
    for fm in fams["semi"]:
        cands.append(dict(kind="semi", fam=fm, seed=seeds["semi"][fm["rep"]]))
    semi_iv = [occ_intervals(x["fam"]) for x in cands]
    by_act = {}
    for i, iv in enumerate(semi_iv):
        for act, t0, t1 in iv:
            by_act.setdefault(act, []).append((t0, t1, i))
    added = 0
    for fm in fams["dint"]:
        iv = occ_intervals(fm)
        near = Counter()
        for act, t0, t1 in iv:
            for s, e, i in by_act.get(act, ()):
                if s - SLACK <= t1 and t0 <= e + SLACK:
                    near[i] += 1
        # covered if the best semitone family overlaps >= LINK of its occurrences
        if near and max(near.values()) >= LINK * len(iv):
            continue
        cands.append(dict(kind="dint", fam=fm, seed=seeds["dint"][fm["rep"]]))
        added += 1
    # Seeds that the pitch-variety rules used to remove (kinds *_simple, see s03_seeds.py) are appended AFTER the earlier
    # candidates so that their ids, which the committed reviewer verdicts refer to, stay the same. A family is added only if
    # fewer than LINK of its occurrences lie where an existing candidate already is (it would add no new place).
    n_old, simple_added = len(cands), 0
    index = {}
    for x in cands:
        for o in x["fam"]["occ"]:
            index.setdefault(o["act"], []).append((o["t0"] - SLACK, o["t1"] + SLACK))
    for kind in ("semi_simple", "dint_simple"):
        path = os.path.join(WORK, f"seeds_{kind}.pkl")
        if not os.path.exists(path):
            continue
        seeds[kind] = pickle.load(open(path, "rb"))
        for fm in pickle.load(open(os.path.join(WORK, f"families_{kind}.pkl"), "rb")):
            iv = occ_intervals(fm)
            hit = sum(1 for act, t0, t1 in iv if any(s0 <= t1 and t0 <= e for s0, e in index.get(act, ())))
            if hit >= LINK * len(iv):
                continue
            cands.append(dict(kind=kind, fam=fm, seed=seeds[kind][fm["rep"]]))
            simple_added += 1
            for act, t0, t1 in iv:
                index.setdefault(act, []).append((t0 - SLACK, t1 + SLACK))
    for i, x in enumerate(cands):
        x["id"] = i
        x["f"] = features(c, x["seed"], x["fam"], x["kind"])
        f = x["f"]
    with open(os.path.join(WORK, "candidates.pkl"), "wb") as fh:
        pickle.dump(cands, fh)
    cols = ["id", "kind", "n", "ic", "n_occ", "passages", "n_scenes", "n_acts", "n_operas", "uniform", "contrast",
            "median_ioi", "stepwise", "pitches", "top_stream_share"]
    with open(os.path.join(WORK, "candidates.tsv"), "w") as fh:
        fh.write("\t".join(cols) + "\n")
        for x in cands:
            row = {**x["f"], "id": x["id"], "kind": x["kind"]}
            fh.write("\t".join(f"{row[k]:.2f}" if isinstance(row[k], float) else str(row[k]) for k in cols) + "\n")
    print(f"{len(fams['semi'])} semitone families + {added} diatonic + {simple_added} formerly pitch-filtered = {len(cands)} candidates")
    sub = [x["f"] for x in cands]
    print("n>=6:", sum(f["n"] >= 6 for f in sub), " n>=8:", sum(f["n"] >= 8 for f in sub),
          " passages>=3:", sum(f["passages"] >= 3 for f in sub), " ops>=2:", sum(f["n_operas"] >= 2 for f in sub))

if __name__ == "__main__":
    main()
