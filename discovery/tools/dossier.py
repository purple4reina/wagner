"""Readable description of a family: the notes of its representative occurrence, and every occurrence with scene,
streams, the time in a recording and what is sung (imported by later steps; also a CLI).
Run: discovery/.venv/bin/python -I discovery/tools/dossier.py <semi|dint> <family number> [max occurrences]
"""
import os
import pickle
import sys
from bisect import bisect_right

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus
from common import ACTS, SHORT, WORK, measure_times, singing

LETTER = "CDEFGAB"
BASE = [0, 2, 4, 5, 7, 9, 11]
_sing = {}
_times = {}


def note_name(pitch, dia):
    step = dia % 7
    octave = dia // 7
    alter = pitch - (12 * (octave + 1) + BASE[step])
    acc = {0: "", 1: "#", 2: "x", -1: "b", -2: "bb"}.get(int(alter), f"{alter:+d}")
    return f"{LETTER[step]}{acc}{octave}"


def sung_at(act, pos0, pos1, near=6.0):
    """Texts sung at score positions pos0..pos1 of the act; if none, the nearest within `near` measures, marked '~'."""
    if act not in _sing:
        rows = sorted(singing(ACTS[act]))
        _sing[act] = (rows, [r[0] for r in rows])
    rows, starts = _sing[act]
    hi = bisect_right(starts, pos1)
    lo = max(0, hi - 12)  # sung lines are short; a line that reaches pos0 starts within the last few lines
    inside = [r for r in rows[lo:hi] if r[1] >= pos0]
    if inside:
        return "; ".join(f"{r[2]}: {r[3]}" for r in inside[:4])
    best = None
    for r in rows[max(0, hi - 6):hi + 6]:
        d = max(r[0] - pos1, pos0 - r[1], 0)
        if d <= near and (best is None or d < best[0]):
            best = (d, r)
    return f"~ {best[1][2]}: {best[1][3]}" if best else ""


def time_at(act, pos):
    if act not in _times:
        _times[act] = measure_times(ACTS[act])
    m = int(pos)
    ts = _times[act]
    m = min(max(m, 1), len(ts) - 1)
    return float(ts[m - 1] + (pos - m) * (ts[m] - ts[m - 1]))


def mmss(sec):
    return f"{int(sec // 60)}:{sec % 60:04.1f}"


def occurrence_row(c, o, scene_key=None):
    """One occurrence of a family merged from its statements -> dict of facts."""
    w0 = min(p[0] for p in o["parts"])
    w1 = max(p[1] for p in o["parts"])
    act = int(c["act"][w0])
    pos0, pos1 = float(c["pos"][w0]), float(c["pos"][w1])
    streams = sorted({str(c["stream_name_of_note"][p[0]]) for p in o["parts"]})
    return dict(act=ACTS[act], act_short=SHORT[ACTS[act]], pos0=pos0, pos1=pos1, measure=int(pos0),
                scene=str(c["scene_key"][c["scene"][w0]]).split(":")[1], streams=streams,
                time=mmss(time_at(act, pos0)), text=sung_at(act, pos0, pos1))


def pattern_notes(c, seed, w0):
    n = seed["n"]
    names = [note_name(int(c["pitch"][i]), int(c["dia"][i])) for i in range(w0, w0 + n)]
    ioi = [round(float(x), 2) for x in c["ioi"][w0:w0 + n - 1]]
    return names, ioi


def show(kind, fi, maxocc=12):
    c = corpus.load()
    seeds = pickle.load(open(os.path.join(WORK, f"seeds_{kind}.pkl"), "rb"))
    fams = pickle.load(open(os.path.join(WORK, f"families_{kind}.pkl"), "rb"))
    fm = fams[fi]
    sd = seeds[fm["rep"]]
    w0 = sd["stm"][0][0]
    names, ioi = pattern_notes(c, sd, w0)
    print(f"family {fi}: {len(fm['occ'])} occurrences, {fm['n_scenes']} scenes, {fm['n_acts']} acts; rep seed n={sd['n']} "
          f"IC={sd['ic']:.0f}, {len(fm['members'])} seeds")
    print("  notes:", " ".join(names[:24]), "..." if len(names) > 24 else "")
    print("  ioi  :", " ".join(str(x) for x in ioi[:24]))
    for o in fm["occ"][:maxocc]:
        r = occurrence_row(c, o)
        print(f"  {r['act_short']:>2} m{r['pos0']:.2f}-{r['pos1']:.2f} sc{r['scene']} {','.join(r['streams'])} {r['time']} | {r['text'][:90]}")


if __name__ == "__main__":
    show(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 12)
