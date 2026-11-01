"""Step 2. Cut the texture of each act into monophonic "streams" that a melody could live in.

A leitmotif is a melody, so we need one note at a time. The piano reduction is polyphonic, so we make several
monophonic views of it and search all of them:
  T1 / T2  top note of part 1 (right hand) / part 2 (left hand)  [skyline]
  B1 / B2  bottom note of part 1 / part 2                         [baseline]
  L<id>    top note of each single line (part, staff, voice), e.g. L111, L211, L112
The skyline respects held notes: a new, lower note under a note that still sounds does not replace it.
Repeated pitches are merged into one note (a tremolo or a pulse is one note, not many), and a stream is cut where
two consecutive notes are more than MAXGAP quarter notes apart (a melody does not continue over a long silence).

Experiment: with the environment variable STREAMS=inner (and WAGNER_WORK pointing to a scratch work directory) only the
second-highest voice of each hand ("U1", "U2": the skyline of the notes the top skyline left over) is built, to test
whether melodies inside chords were missed (see explore/e14_inner_voice_probe.sh).
Output: discovery/work/streams/<act>.npz, one row per stream note:
  stream (int code), seg (segment id, unique per act), pitch, dia, t (quarter notes from the start of the act),
  measure (1-based), pos (measure + onset / measure length, the 3-digit fractional position used by the
  annotations), ioi (quarter notes to the next note of the segment; 0 for the last note of a segment).
Run: python3 -I discovery/tools/s02_streams.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ACTS, WORK, load_notes

MAXGAP = 12.0  # quarter notes
MIN_LINE_NOTES = 150  # ignore lines with fewer notes (a stray voice is not a melody)


def skyline(t, p, dia, meas, dur, top=True):
    """Monophonic reduction of a set of notes (sorted by time). Returns indices of the notes kept."""
    sign = 1 if top else -1
    keep = []
    # group by onset
    n = len(t)
    i = 0
    sounding_end = -1.0
    sounding_p = None
    while i < n:
        j = i
        while j < n and t[j] == t[i]:
            j += 1
        grp = range(i, j)
        best = max(grp, key=lambda k: sign * p[k])
        if sounding_p is None or t[i] >= sounding_end - 1e-9 or sign * p[best] >= sign * sounding_p:
            keep.append(best)
            sounding_p = p[best]
            sounding_end = t[best] + dur[best]
        i = j
    return keep


def build_stream(t, p, dia, meas, pos, dur, keep):
    """Merge repeated pitches, cut at long gaps. Returns arrays for this stream plus segment ids."""
    rows = []
    for k in keep:
        if rows and p[rows[-1]] == p[k]:
            continue
        rows.append(k)
    rows = np.array(rows, dtype=int)
    if len(rows) == 0:
        return None
    tt = t[rows]
    gap = np.diff(tt, append=np.inf)
    ioi = np.where(gap > MAXGAP, 0.0, gap)
    seg = np.concatenate([[0], np.cumsum(gap[:-1] > MAXGAP)])
    return dict(pitch=p[rows], dia=dia[rows], t=tt, measure=meas[rows], pos=pos[rows], ioi=ioi, seg=seg)


def main():
    os.makedirs(os.path.join(WORK, "streams"), exist_ok=True)
    names_out = {}
    for act in ACTS:
        d = load_notes(act)
        cum = np.concatenate([[0.0], np.cumsum(d["mlen"])])
        meas, onset = d["measure"], d["onset"]
        t_all = cum[meas - 1] + onset
        pos_all = meas + onset / d["mlen"][meas - 1]
        part = d["line"] // 100
        views = []
        for pt in (1, 2):
            views.append((f"T{pt}", part == pt, True))
            views.append((f"B{pt}", part == pt, False))
        for ln in np.unique(d["line"]):
            if (d["line"] == ln).sum() >= MIN_LINE_NOTES:
                views.append((f"L{ln}", d["line"] == ln, True))
        inner = os.environ.get("STREAMS") == "inner"
        if inner:
            views = [(f"U{pt}", part == pt, True) for pt in (1, 2)]
        cols = {k: [] for k in ("stream", "seg", "pitch", "dia", "t", "measure", "pos", "ioi")}
        names = []
        seg_base = 0
        for name, mask, top in views:
            idx = np.nonzero(mask)[0]
            order = np.lexsort((d["pitch"][idx], t_all[idx]))
            idx = idx[order]
            t, p, dia, ms, ps, du = (t_all[idx], d["pitch"][idx], d["dia"][idx], meas[idx], pos_all[idx], d["dur"][idx])
            keep = skyline(t, p, dia, ms, du, top)
            if inner:  # second voice: the skyline of what the top skyline left over
                rest = np.setdiff1d(np.arange(len(t)), keep)
                keep = [int(rest[k]) for k in skyline(t[rest], p[rest], dia[rest], ms[rest], du[rest], True)]
            s = build_stream(t, p, dia, ms, ps, du, keep)
            if s is None:
                continue
            names.append(name)
            cols["stream"].append(np.full(len(s["pitch"]), len(names) - 1, dtype=np.int16))
            cols["seg"].append(s["seg"] + seg_base)
            seg_base += int(s["seg"].max()) + 1
            for k in ("pitch", "dia", "t", "measure", "pos", "ioi"):
                cols[k].append(s[k])
        out = {k: np.concatenate(v) for k, v in cols.items()}
        out["names"] = np.array(names)
        np.savez_compressed(os.path.join(WORK, "streams", f"{act}.npz"), **out)
        print(f"{act}: {len(out['pitch'])} stream notes in {len(names)} streams ({' '.join(names)})")


if __name__ == "__main__":
    main()
