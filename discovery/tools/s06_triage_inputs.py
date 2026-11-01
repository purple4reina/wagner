"""Step 6. Write compact dossier text for the candidates in the review pool, in batches for reviewers.

Candidates are ordered by where their first occurrence lies in the score (act, time), so that candidates that
overlap in the score land in the same batch and a reviewer can notice that two are the same motif.
Each block: id, length, occurrences/scenes/operas, the notes of one occurrence, and up to 4 occurrences chosen from
different scenes with the text sung there ("~" = nearest text). Durations and any rhythm-derived label are NOT shown:
the miner already guarantees that the occurrences of a pattern have similar rhythm, and reviewers must not judge a
pattern by how varied its durations are. (Review rounds 1 and 2 used an older format with a "[figuration]/[motif]" tag
and a durations line; those dossiers are archived in decisions/archive_round1_2_dossiers/.)
Result: work/triage/batch_NN.txt.  Run: discovery/.venv/bin/python -I discovery/tools/s06_triage_inputs.py [batch size [ids file [first batch number [samples]]]]
With an ids file only those candidates are written, numbered from the first batch number 
Round 3 (blind): `s06 120 decisions/round3_ids.txt 12 4`.
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
import dossier
from common import WORK

PER_BATCH = 112


def block(c, x, samples=4):
    f = x["f"]
    names, ioi = dossier.pattern_notes(c, x["seed"], x["seed"]["stm"][0][0])
    seen, picks = set(), []
    for o in x["fam"]["occ"]:  # prefer occurrences in scenes not yet shown
        sc = (o["act"], int(c["scene"][o["parts"][0][0]]))
        if sc not in seen:
            seen.add(sc)
            picks.append(o)
    picks = (picks + [o for o in x["fam"]["occ"] if o not in picks])[:samples]
    lines = [f"#{x['id']} n={f['n']} occ={f['n_occ']} scenes={f['n_scenes']} ops={f['n_operas']} "
             f"streams={'/'.join(sorted({s for o in x['fam']['occ'] for s in dossier.occurrence_row(c, o)['streams']})[:3])}",
             "  notes: " + " ".join(names[:16]) + (" ..." if len(names) > 16 else "")]
    for o in sorted(picks, key=lambda o: (o["act"], o["t0"])):
        r = dossier.occurrence_row(c, o)
        lines.append(f"  - {r['act_short']} m{r['measure']} sc{r['scene']}: {r['text'][:60]}")
    return "\n".join(lines)


def main(per_batch=PER_BATCH, ids_file=None, first=1, samples=4):
    c = corpus.load()
    pool = pickle.load(open(os.path.join(WORK, "pool.pkl"), "rb"))
    if ids_file:
        keep = {int(i) for i in open(ids_file).read().split()}
        by_id = {x["id"]: x for x in pool}
        pool = [x for x in pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb")) if x["id"] in keep]
    pool.sort(key=lambda x: (x["fam"]["occ"][0]["act"], x["fam"]["occ"][0]["t0"]))
    os.makedirs(os.path.join(WORK, "triage"), exist_ok=True)
    nb = (len(pool) + per_batch - 1) // per_batch
    for b in range(nb):
        chunk = pool[b * per_batch:(b + 1) * per_batch]
        with open(os.path.join(WORK, "triage", f"batch_{first + b:02d}.txt"), "w") as fh:
            fh.write("\n".join(block(c, x, samples) for x in chunk) + "\n")
    print(f"{len(pool)} candidates in {nb} batches, numbered from {first:02d}")


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else PER_BATCH, a[2] if len(a) > 2 else None, int(a[3]) if len(a) > 3 else 1, int(a[4]) if len(a) > 4 else 4)
