"""Explore: which accepted groups look like the same leitmotif (shared locations or shared interval runs)?"""
import json, glob, os, sys
from difflib import SequenceMatcher
rows = {}
for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "leitmotifs", "*.json"))):
    d = json.load(open(f)); rows[d["id"]] = d
ids = sorted(rows)
def share(a, b):
    A, B = rows[a]["occurrences"], rows[b]["occurrences"]
    small, big = (A, B) if len(A) <= len(B) else (B, A)
    hit = sum(1 for o in small if any(p["act"] == o["act"] and p["pos0"] - 1 <= o["pos1"] and o["pos0"] <= p["pos1"] + 1 for p in big))
    return hit / len(small)
def seq(a, b):
    x, y = rows[a]["pattern_intervals"], rows[b]["pattern_intervals"]
    m = SequenceMatcher(None, x, y, autojunk=False).find_longest_match(0, len(x), 0, len(y))
    return m.size / max(1, min(len(x), len(y))), m.size
out = []
for i, a in enumerate(ids):
    for b in ids[i + 1:]:
        s = share(a, b); q, qs = seq(a, b)
        if s >= 0.4 or (q >= 0.8 and qs >= 5):
            out.append((a, b, s, q, qs))
print(len(out), "pairs")
for a, b, s, q, qs in out[:60]:
    print(f"{a} {b} share={s:.2f} seqcover={q:.2f}({qs}) n={rows[a]['n_notes']},{rows[b]['n_notes']} occ={rows[a]['n_occurrences']},{rows[b]['n_occurrences']}")
