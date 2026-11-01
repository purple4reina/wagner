"""Whole-cycle corpus of stream notes with the token arrays used for matching (imported by the s03+ steps).

All acts are concatenated; a "segment" (an unbroken run of one stream, see s02_streams.py) never crosses an act.
For stream note i (all arrays have one entry per stream note):
  semi[i]  interval to the next note in semitones, clipped to +-15, offset by +15 (0..30); 31 = no next note
  dint[i]  diatonic interval to the next note (steps; 7 = an octave; accidentals ignored), clipped to +-9, offset +9
  rc[i]    rhythm class: how long note i lasts (inter-onset interval) relative to note i-1:
             0 much shorter (<0.42x)  1 shorter (<0.73x)  2 about the same  3 longer (>1.37x)  4 much longer (>2.4x)
           5 = unknown (first or last note of a segment)
A window of n notes starting at s is valid when all n notes are in one segment. It is described by the n-1 intervals
semi[s..s+n-2] and the n-2 rhythm classes rc[s+1..s+n-2].
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ACTS, WORK, load_notes, scene_of_measure  # noqa: F401

RC_EDGES = np.log2([0.42, 0.73, 1.37, 2.4])
CACHE = os.path.join(WORK, "corpus.npz")


def rhythm_class(ioi, seg):
    n = len(ioi)
    rc = np.full(n, 5, dtype=np.int8)
    ok = np.zeros(n, dtype=bool)
    ok[1:] = (ioi[1:] > 0) & (ioi[:-1] > 0) & (seg[1:] == seg[:-1])
    ratio = np.ones(n)
    ratio[1:] = ioi[1:] / np.where(ioi[:-1] > 0, ioi[:-1], 1)
    cls = np.digitize(np.log2(np.maximum(ratio, 1e-6)), RC_EDGES)
    rc[ok] = cls[ok]
    return rc


def build():
    parts = {k: [] for k in ("act", "scene", "stream", "seg", "pitch", "dia", "t", "measure", "pos", "ioi")}
    seg_base = 0
    scene_ids = {}
    stream_names = []
    for ai, act in enumerate(ACTS):
        z = np.load(os.path.join(WORK, "streams", f"{act}.npz"))
        names = [str(x) for x in z["names"]]
        sc = scene_of_measure(act)
        lab = [sc[m] if m < len(sc) else "" for m in z["measure"]]
        sid = np.array([scene_ids.setdefault((ai, l), len(scene_ids)) for l in lab], dtype=np.int16)
        parts["act"].append(np.full(len(sid), ai, dtype=np.int8))
        parts["scene"].append(sid)
        parts["stream"].append(z["stream"])
        parts["seg"].append(z["seg"] + seg_base)
        seg_base += int(z["seg"].max()) + 1
        for k in ("pitch", "dia", "t", "measure", "pos", "ioi"):
            parts[k].append(z[k])
        stream_names.append(names)
    c = {k: np.concatenate(v) for k, v in parts.items()}
    seg, p, dia = c["seg"], c["pitch"], c["dia"]
    same = np.zeros(len(p), dtype=bool)
    same[:-1] = seg[:-1] == seg[1:]
    semi = np.full(len(p), 31, dtype=np.int8)
    dint = np.full(len(p), 31, dtype=np.int8)
    d1 = np.zeros(len(p), dtype=np.int64)
    d2 = np.zeros(len(p), dtype=np.int64)
    d1[:-1] = p[1:] - p[:-1]
    d2[:-1] = dia[1:] - dia[:-1]
    semi[same] = np.clip(d1[same], -15, 15) + 15
    dint[same] = np.clip(d2[same], -9, 9) + 9
    c["semi"], c["dint"] = semi, dint
    c["rc"] = rhythm_class(c["ioi"], seg)
    c["scene_key"] = np.array([f"{ACTS[a]}:{s}" for (a, s), _ in sorted(scene_ids.items(), key=lambda kv: kv[1])])
    c["stream_names"] = np.array([n for names in stream_names for n in names])
    # global stream-name index: per act the stream codes are local, store (act, local) -> name
    c["stream_name_of_note"] = np.array(
        [stream_names[a][s] for a, s in zip(c["act"].tolist(), c["stream"].tolist())])
    return c


def load():
    if not os.path.exists(CACHE):
        np.savez_compressed(CACHE, **build())
    z = np.load(CACHE)
    return {k: z[k] for k in z.files}


if __name__ == "__main__":
    c = build()
    np.savez_compressed(CACHE, **c)
    print(len(c["pitch"]), "stream notes;", len(c["scene_key"]), "scenes;", int(c["seg"].max()) + 1, "segments")
