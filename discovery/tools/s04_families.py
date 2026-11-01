"""Step 4. Merge seeds that come together into families (= leitmotif candidates).

Two seeds are linked when most statements of each lie where the statements of the other lie (overlapping in time, or
touching within SLACK quarter notes): LINK of the statements of A overlap a statement of B and vice versa. A seed
that is only part of a longer one but also occurs alone elsewhere is not linked (it is a motif of its own).
Linked seeds form connected components = families. For each family we merge all statements of all its seeds into
occurrences (overlapping or within GAP quarter notes = one occurrence) and compute features.
Result: discovery/work/families_<kind>.pkl and families_<kind>.tsv (one line per family, for eyeballing).
Run: discovery/.venv/bin/python -I discovery/tools/s04_families.py <semi|dint>
"""
import os
import pickle
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
from common import ACTS, OPERA, SHORT, WORK

SLACK = 1.0  # quarter notes
GAP = 4.0
LINK = 0.6


def overlaps(statements):
    """statements: list of (act, t0, t1, seed). Returns dict (seedA, seedB) -> set of statement ids of A overlapping B."""
    order = sorted(range(len(statements)), key=lambda i: (statements[i][0], statements[i][1]))
    hit = defaultdict(set)
    active = []  # ids whose t1 + SLACK >= current t0
    cur_act = None
    for i in order:
        act, t0, t1, seed = statements[i]
        if act != cur_act:
            active, cur_act = [], act
        active = [j for j in active if statements[j][2] + SLACK >= t0]
        for j in active:
            sj = statements[j][3]
            if sj != seed:
                hit[(seed, sj)].add(i)
                hit[(sj, seed)].add(j)
        active.append(i)
    return hit


def main(kind):
    c = corpus.load()
    with open(os.path.join(WORK, f"seeds_{kind}.pkl"), "rb") as f:
        seeds = pickle.load(f)
    stm = []  # (act, t0, t1, seed index)
    for si, sd in enumerate(seeds):
        for w0, w1 in sd["stm"]:
            stm.append((int(c["act"][w0]), float(c["t"][w0]), float(c["t"][w1]), si))
    cnt = np.array([len(sd["stm"]) for sd in seeds])
    hit = overlaps(stm)
    parent = list(range(len(seeds)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (a, b), ids in hit.items():
        if a < b and len(ids) >= LINK * cnt[a] and len(hit.get((b, a), ())) >= LINK * cnt[b] and len(ids) >= 2:
            parent[find(a)] = find(b)
    comp = defaultdict(list)
    for i in range(len(seeds)):
        comp[find(i)].append(i)
    fams = []
    for members in comp.values():
        occ_raw = [(int(c["act"][w0]), float(c["t"][w0]), float(c["t"][w1]), w0, w1, si)
                   for si in members for w0, w1 in seeds[si]["stm"]]
        occ_raw.sort()
        occ = []
        for act, t0, t1, w0, w1, si in occ_raw:
            if occ and occ[-1]["act"] == act and t0 <= occ[-1]["t1"] + GAP:
                o = occ[-1]
                o["t1"] = max(o["t1"], t1)
                o["parts"].append((w0, w1, si))
            else:
                occ.append(dict(act=act, t0=t0, t1=t1, parts=[(w0, w1, si)]))
        scenes = {int(c["scene"][o["parts"][0][0]]) for o in occ}
        acts = {o["act"] for o in occ}
        operas = {OPERA[ACTS[a]] for a in acts}
        rep = max(members, key=lambda i: (seeds[i]["n"], seeds[i]["ic"]))
        if len(occ) >= 3 and len(scenes) >= 2:
            fams.append(dict(kind=kind, members=members, rep=rep, occ=occ, n_scenes=len(scenes), n_acts=len(acts),
                             n_operas=len(operas)))
    fams.sort(key=lambda f: (-seeds[f["rep"]]["n"], -seeds[f["rep"]]["ic"]))
    with open(os.path.join(WORK, f"families_{kind}.pkl"), "wb") as f:
        pickle.dump(fams, f)
    with open(os.path.join(WORK, f"families_{kind}.tsv"), "w") as f:
        f.write("fam\tn\tic\tseeds\toccurrences\tscenes\tacts\toperas\tfirst_locations\n")
        for i, fm in enumerate(fams):
            sd = seeds[fm["rep"]]
            locs = ",".join(f"{SHORT[ACTS[o['act']]]}:{int(c['measure'][o['parts'][0][0]])}" for o in fm["occ"][:6])
            f.write(f"{i}\t{sd['n']}\t{sd['ic']:.0f}\t{len(fm['members'])}\t{len(fm['occ'])}\t{fm['n_scenes']}\t"
                    f"{fm['n_acts']}\t{fm['n_operas']}\t{locs}\n")
    sizes = np.array([len(fm["members"]) for fm in fams])
    print(f"{len(seeds)} seeds -> {len(fams)} families; seeds per family: median {np.median(sizes):.0f}, max {sizes.max()}")
    print("occurrences per family: median", int(np.median([len(fm['occ']) for fm in fams])),
          " max", max(len(fm['occ']) for fm in fams))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "semi")
