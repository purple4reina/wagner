"""Step 1. Read the piano-reduction MusicXML of each act into flat note arrays.

Output: discovery/work/notes/<act>.npz with one entry per note (ties merged into the first note):
  measure  1-based measure number (= row number in the annotation files, not the printed number)
  onset    quarter notes from the start of the measure
  dur      length in quarter notes (tied notes summed, may run past the barline)
  pitch    MIDI number
  dia      diatonic step number (7 * octave + C D E F G A B index): intervals that ignore the accidental
  line     id of (part, staff, voice) as 100*part + 10*staff + voice
  mlen     (separate array, one per measure) nominal length of the measure in quarter notes
Grace notes are dropped. Run: python3 -I discovery/tools/s01_parse_score.py
"""
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ACTS, DATA, WORK

STEP = {"C": (0, 0), "D": (2, 1), "E": (4, 2), "F": (5, 3), "G": (7, 4), "A": (9, 5), "B": (11, 6)}


def parse(path):
    cols = {k: [] for k in ("measure", "onset", "dur", "pitch", "dia", "line")}
    mlen = {}
    open_tie = {}  # (line, pitch) -> row index of the note that a later tie-stop extends
    part_no = 0
    divisions = 256
    beats, beat_type = 4, 4
    for event, el in ET.iterparse(path, events=("end",)):
        if el.tag != "part":
            continue
        part_no += 1
        cursor_m = 0
        for meas in el.findall("measure"):
            cursor_m += 1
            for attr in meas.findall("attributes"):
                d = attr.find("divisions")
                if d is not None:
                    divisions = int(d.text)
                t = attr.find("time")
                if t is not None:
                    beats, beat_type = int(t.find("beats").text.split("+")[0]), int(t.find("beat-type").text)
            if part_no == 1:
                mlen[cursor_m] = beats * 4.0 / beat_type
            pos = 0  # in divisions
            last_onset = 0
            last_line = None
            for ch in meas:
                if ch.tag == "backup":
                    pos -= int(ch.find("duration").text)
                elif ch.tag == "forward":
                    pos += int(ch.find("duration").text)
                elif ch.tag == "note":
                    if ch.find("grace") is not None:
                        continue
                    dur = int(ch.find("duration").text) if ch.find("duration") is not None else 0
                    is_chord = ch.find("chord") is not None
                    onset = last_onset if is_chord else pos
                    if not is_chord:
                        last_onset = pos
                        pos += dur
                    p = ch.find("pitch")
                    if p is None:  # rest
                        continue
                    staff = int(ch.findtext("staff", "1"))
                    voice = int(ch.findtext("voice", "1"))
                    line = 100 * part_no + 10 * staff + voice
                    step, dstep = STEP[p.findtext("step")]
                    alter = int(float(p.findtext("alter", "0")))
                    octave = int(p.findtext("octave"))
                    pitch = 12 * (octave + 1) + step + alter
                    dia = 7 * octave + dstep
                    ties = {t.get("type") for t in ch.findall("tie")}
                    key = (line, pitch)
                    if "stop" in ties and key in open_tie:
                        cols["dur"][open_tie[key]] += dur / divisions
                        if "start" not in ties:
                            del open_tie[key]
                        continue
                    idx = len(cols["pitch"])
                    cols["measure"].append(cursor_m)
                    cols["onset"].append(onset / divisions)
                    cols["dur"].append(dur / divisions)
                    cols["pitch"].append(pitch)
                    cols["dia"].append(dia)
                    cols["line"].append(line)
                    if "start" in ties:
                        open_tie[key] = idx
        el.clear()
    out = {k: np.array(v, dtype=np.float64 if k in ("onset", "dur") else np.int32) for k, v in cols.items()}
    out["mlen"] = np.array([mlen[i] for i in range(1, max(mlen) + 1)], dtype=np.float64)
    return out


def main():
    os.makedirs(os.path.join(WORK, "notes"), exist_ok=True)
    for act in ACTS:
        d = parse(os.path.join(DATA, "01_RawData", "score_musicxml", f"Wagner_{act}.xml"))
        order = np.lexsort((d["pitch"], d["line"], d["onset"], d["measure"]))
        for k in ("measure", "onset", "dur", "pitch", "dia", "line"):
            d[k] = d[k][order]
        np.savez_compressed(os.path.join(WORK, "notes", f"{act}.npz"), **d)
        print(f"{act}: {len(d['pitch'])} notes, {len(d['mlen'])} measures, {len(set(d['line'].tolist()))} lines")


if __name__ == "__main__":
    main()
