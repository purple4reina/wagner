"""Step 7c. Merge groups that are one leitmotif: patterns that "come up together", and variants of one pattern.

Run after s07b (and s07_expand, so approximate occurrences count). For two groups X, Y with |occ(X)| <= |occ(Y)|:
  * ATTACH: at least ATTACH of X's occurrences overlap occurrences of Y (within 1 quarter note) -> X has no life of
    its own, it is a part of (or an accompaniment to) Y, and the groups are merged;
  * VARIANT: the longest common run of intervals is >= RUN intervals and covers >= COVER of the shorter pattern (same
    interval alphabet) -> two statements of one idea with different beginnings/continuations; merged.
Merged groups keep every member candidate, so all patterns remain listed. Reads decisions/groups_unmerged.tsv (from s07b), writes decisions/groups_auto.tsv and renumbers LM001... by length.
Run: discovery/.venv/bin/python -I discovery/tools/s07c_merge_groups.py
"""
import os
import pickle
import shutil
import sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DECISIONS, WORK
import s08_build

ATTACH = 0.75
RUN = 6
COVER = 0.85
SLACK = 1.0


def main():
    src = os.path.join(DECISIONS, "groups_unmerged.tsv")
    auto = os.path.join(DECISIONS, "groups_auto.tsv")
    shutil.copy(src, auto)  # always merge from the unmerged groups, so reruns give the same result
    groups = s08_build.read_groups()
    cands = {x["id"]: x for x in pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))}
    exp_path = os.path.join(WORK, "expansions.pkl")
    expansions = pickle.load(open(exp_path, "rb")) if os.path.exists(exp_path) else {}
    occ = {lm: s08_build.merged_occurrences(g, cands, expansions) for lm, g in groups.items()}
    by_act = {}
    for lm, os_ in occ.items():
        by_act[lm] = {}
        for o in os_:
            by_act[lm].setdefault(o["act"], []).append((o["t0"] - SLACK, o["t1"] + SLACK))

    def share(x, y):
        hit = sum(1 for o in occ[x] if any(s <= o["t1"] and o["t0"] <= e for s, e in by_act[y].get(o["act"], ())))
        return hit / len(occ[x])

    ids = sorted(groups)
    parent = {i: i for i in ids}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    log = []
    for a_i, a in enumerate(ids):
        for b in ids[a_i + 1:]:
            x, y = (a, b) if len(occ[a]) <= len(occ[b]) else (b, a)
            s = share(x, y)
            ra, rb = cands[groups[a]["rep"]], cands[groups[b]["rep"]]
            q = 0.0
            if ra["kind"].startswith("dint") == rb["kind"].startswith("dint"):  # same interval alphabet
                ia, ib = ra["seed"]["tokens"][0], rb["seed"]["tokens"][0]
                m = SequenceMatcher(None, ia, ib, autojunk=False).find_longest_match(0, len(ia), 0, len(ib))
                q = m.size / max(1, min(len(ia), len(ib))) if m.size >= RUN else 0.0
            if s >= ATTACH or q >= COVER:
                parent[find(a)] = find(b)
                log.append(f"{a} {b} attach_share={s:.2f} variant_cover={q:.2f}")
    merged = {}
    for i in ids:
        merged.setdefault(find(i), []).append(i)
    rows = []
    for members in merged.values():
        cand_ids = sorted({m for lm in members for m in groups[lm]["members"]})
        rep = max((groups[lm]["rep"] for lm in members), key=lambda r: (cands[r]["f"]["n"], cands[r]["f"]["ic"]))
        themes = "; ".join(t for t in dict.fromkeys(groups[lm]["themes"] for lm in members) if t)[:300]
        rows.append((rep, cand_ids, themes))
    rows.sort(key=lambda r: (-cands[r[0]]["f"]["n"], -cands[r[0]]["f"]["ic"]))
    with open(auto, "w", encoding="utf-8") as fh:
        fh.write("lm\trep\tmembers\treviewer_themes\n")
        for k, (rep, cand_ids, themes) in enumerate(rows, 1):
            fh.write(f"LM{k:03d}\t{rep}\t{','.join(map(str, cand_ids))}\t{themes}\n")
    open(os.path.join(DECISIONS, "merge_log.txt"), "w").write("\n".join(log) + "\n")
    sizes = sorted((len(m) for m in merged.values()), reverse=True)
    print(f"{len(ids)} groups -> {len(rows)} after {len(log)} merge links; largest merged sets (in groups): {sizes[:8]}")


if __name__ == "__main__":
    main()
