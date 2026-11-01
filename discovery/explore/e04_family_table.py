"""Explore: one compact line per family so a sample can be read quickly.
Run: discovery/.venv/bin/python -I discovery/explore/e04_family_table.py <kind> <first> <count> [step]
"""
import os, pickle, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import corpus
from common import ACTS, SHORT, WORK
kind, first, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
step = int(sys.argv[4]) if len(sys.argv) > 4 else 1
c = corpus.load()
seeds = pickle.load(open(os.path.join(WORK, f"seeds_{kind}.pkl"), "rb"))
fams = pickle.load(open(os.path.join(WORK, f"families_{kind}.pkl"), "rb"))
off = 15 if kind == "semi" else 9
for i in range(first, min(first + count * step, len(fams)), step):
    fm = fams[i]; sd = seeds[fm["rep"]]
    ints = " ".join(f"{x-off:+d}" for x in sd["tokens"][0][:20])
    io = sd["tokens"][0]
    w = sd["stm"][0][0]
    ioi = " ".join(f"{x:g}" for x in np.round(c["ioi"][w:w + sd["n"] - 1][:20], 2))
    acts = "".join(sorted({SHORT[ACTS[o['act']]][0] for o in fm["occ"]}))
    print(f"#{i} n={sd['n']} ic={sd['ic']:.0f} occ={len(fm['occ'])} sc={fm['n_scenes']} ops={acts} seeds={len(fm['members'])} | {ints} | {ioi}")
