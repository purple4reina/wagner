"""Step 7b. Read the reviewers' verdicts and group candidates that are the same leitmotif.

Inputs: work/pool.pkl, work/candidates.pkl, decisions/triage_batch_*.tsv (and optionally decisions/review2_*.tsv with
the same columns, which override earlier verdicts for the same id) and decisions/rule_*.tsv (acceptances made by rule).
Accepted = label M (later batch files override earlier verdicts for the same id; round 3, batches 12+, is blind to
rhythm and supersedes the F/G/U labels of rounds 1-2). Two accepted candidates are joined when a reviewer said `same_as` (either direction) AND the data
agree: at least SHARE of the smaller one's occurrences overlap occurrences of the other (within 1 quarter note), or the
longest common run of intervals covers >= SEQ of the shorter pattern. Joined candidates form a group (connected
components); the group's pattern is that of its longest member.
Outputs: decisions/groups_unmerged.tsv (s07c merges them further into groups_auto.tsv), work/accepted_ids.txt (ids for s07_expand).
Run: discovery/.venv/bin/python -I discovery/tools/s07b_group.py
"""
import glob
import os
import pickle
import sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DECISIONS, WORK

SHARE = 0.34
SEQ = 0.75
SLACK = 1.0


def load_verdicts(rules=True):
    """Reviewer verdicts (decisions/triage_batch_*.tsv), then, if `rules`, the acceptances made by rule (rule_*.tsv).
    Later files override earlier ones for the same id."""
    v = {}
    files = sorted(glob.glob(os.path.join(DECISIONS, "triage_batch_*.tsv"))) + \
        sorted(glob.glob(os.path.join(DECISIONS, "review2_*.tsv"))) + \
        (sorted(glob.glob(os.path.join(DECISIONS, "rule_*.tsv"))) if rules else [])
    for fn in files:
        for line in open(fn, encoding="utf-8").read().splitlines()[1:]:
            p = line.split("\t")
            if len(p) < 2 or not p[0].strip().isdigit():
                continue
            same = [int(x) for x in (p[3] if len(p) > 3 else "-").replace(" ", "").split(",") if x.isdigit()]
            v[int(p[0])] = dict(label=p[1].strip(), theme=p[2].strip() if len(p) > 2 else "-", same=same)
    return v


def overlap_share(a, b):
    """Fraction of the occurrences of the smaller candidate that overlap an occurrence of the other."""
    small, big = (a, b) if len(a["fam"]["occ"]) <= len(b["fam"]["occ"]) else (b, a)
    iv = {}
    for o in big["fam"]["occ"]:
        iv.setdefault(o["act"], []).append((o["t0"] - SLACK, o["t1"] + SLACK))
    hit = sum(1 for o in small["fam"]["occ"] if any(s <= o["t1"] and o["t0"] <= e for s, e in iv.get(o["act"], ())))
    return hit / len(small["fam"]["occ"])


def seq_cover(a, b):
    ia, ib = a["seed"]["tokens"][0], b["seed"]["tokens"][0]
    m = SequenceMatcher(None, ia, ib, autojunk=False).find_longest_match(0, len(ia), 0, len(ib))
    return m.size / max(1, min(len(ia), len(ib)))


def main():
    verdicts = load_verdicts()
    cands = {x["id"]: x for x in pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))}
    accepted = sorted(i for i, v in verdicts.items() if v["label"] == "M" and i in cands)
    parent = {i: i for i in accepted}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    reasons = {}
    for i in accepted:
        for j in verdicts[i]["same"]:
            if j in parent and j != i:
                s, q = overlap_share(cands[i], cands[j]), seq_cover(cands[i], cands[j])
                if s >= SHARE or q >= SEQ:
                    parent[find(i)] = find(j)
                    reasons[(min(i, j), max(i, j))] = f"share={s:.2f} seq={q:.2f}"
    groups = {}
    for i in accepted:
        groups.setdefault(find(i), []).append(i)
    rows = []
    for k, members in enumerate(sorted(groups.values(), key=lambda m: -max(cands[i]["f"]["n"] for i in m)), 1):
        rep = max(members, key=lambda i: (cands[i]["f"]["n"], cands[i]["f"]["ic"]))
        themes = sorted({verdicts[i]["theme"] for i in members if verdicts[i]["theme"] not in ("-", "")})
        rows.append((f"LM{k:03d}", rep, members, "; ".join(themes)[:200]))
    with open(os.path.join(DECISIONS, "groups_unmerged.tsv"), "w", encoding="utf-8") as fh:
        fh.write("lm\trep\tmembers\treviewer_themes\n")
        for lm, rep, members, th in rows:
            fh.write(f"{lm}\t{rep}\t{','.join(map(str, members))}\t{th}\n")
    open(os.path.join(WORK, "accepted_ids.txt"), "w").write(" ".join(str(r[1]) for r in rows) + "\n")
    import shutil
    shutil.copy(os.path.join(DECISIONS, 'groups_unmerged.tsv'), os.path.join(DECISIONS, 'groups_auto.tsv'))
    sizes = sorted((len(r[2]) for r in rows), reverse=True)
    print(f"verdicts {len(verdicts)}; accepted M {len(accepted)} -> {len(rows)} groups (largest {sizes[:6]}); "
          f"labels:", {l: sum(1 for v in verdicts.values() if v['label'] == l) for l in 'MFGU'})


if __name__ == "__main__":
    main()
