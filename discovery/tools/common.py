"""Shared paths and helpers for the discovery pipeline. Needs only Python 3 and numpy."""
import csv
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
WORK = os.environ.get("WAGNER_WORK") or os.path.join(ROOT, "discovery", "work")  # override for side experiments
RESULTS = os.path.join(ROOT, "discovery", "results")
DECISIONS = os.path.join(ROOT, "discovery", "decisions")

ACTS = ["WWV086A", "WWV086B-1", "WWV086B-2", "WWV086B-3", "WWV086C-1", "WWV086C-2",
        "WWV086C-3", "WWV086D-0", "WWV086D-1", "WWV086D-2", "WWV086D-3"]
SHORT = {a: a[6:] for a in ACTS}  # "A", "B-1", ...
SHORT = {a: s.replace("-", "") for a, s in SHORT.items()}  # "A", "B1", ..., "D0"
OPERA = {a: SHORT[a][0] for a in ACTS}  # A=Rheingold B=Walkure C=Siegfried D=Gotterdammerung
TIME_RECORDING = "Karajan1966"  # one of the 3 recordings with hand-corrected measure times


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def scenes(act):
    """[(start_measure, end_measure, scene)] with 1-based measure numbers (end is inclusive)."""
    rows = read_csv(os.path.join(DATA, "02_Annotations", "ann_score_scenes", f"Wagner_{act}.csv"))
    return [(float(r["measure_start"]), float(r["measure_end"]), r["scene"]) for r in rows]


def scene_of_measure(act):
    """Array scene_of[m] (index 0 unused) giving the scene label of measure m; '' if outside any scene."""
    sc = scenes(act)
    n = int(sc[-1][1]) + 2
    out = [""] * n
    for s, e, lab in sc:
        for m in range(int(s), min(int(e) + 1, n)):
            out[m] = lab
    return out


def singing(act):
    """[(start, end, person, text)] score positions (float, measure.fraction)."""
    rows = read_csv(os.path.join(DATA, "02_Annotations", "ann_score_singing", f"Wagner_{act}.csv"))
    return [(float(r["measure_start"]), float(r["measure_end"]), r["person"], r["text"]) for r in rows]


def measure_times(act, recording=TIME_RECORDING):
    """Seconds at which each measure begins (index 0 = measure 1). Last entry is the end of the act."""
    rows = read_csv(os.path.join(DATA, "02_Annotations", "ann_audio_measure", f"Wagner_{act}_{recording}.csv"))
    return np.array([float(r["start"]) for r in rows])


def load_notes(act):
    z = np.load(os.path.join(WORK, "notes", f"{act}.npz"))
    return {k: z[k] for k in z.files}
