"""Find a melody in the piano score of the Wagner Ring Dataset and write the motif data
file that leitmotifs/index.html reads (format: leitmotifs/DATA-SPEC.md).

Each passage has a level that tells how close it is to the melody (see LEVELS). All notes of a
passage are in one staff and voice, they follow each other with no gap, and tied notes are merged.
The notation excerpt of a passage is copied from the score (see excerpt()).

usage: python3 -I tools/find_motif.py [--data DIR] [--out FILE] [--closest N]
"""
import argparse, copy, csv, json, math, pathlib, re
import xml.etree.ElementTree as ET
from bisect import bisect_right
from collections import defaultdict
from fractions import Fraction
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parent.parent
MOTIF_ID, MOTIF_NAME = "siegfried", "Siegfried"
MOTIF_LY = "g,8 c4. ~c4 c8 es4. d4 c8 aes2. c4. bes,4 aes,8 es4. ~es4 es8 f4. ~f8 es8 f8 g2."
CORE = (1, 13)  # the notes of MOTIF_LY that level 2 looks for: notes 2 to 13
LEVELS = [
    dict(level=1, name="Closest to the original",
         description="The best partial matches of the whole phrase. The pitches and the rhythm are the same, in any octave."),
    dict(level=2, name="Same core pitches",
         description="Notes 2 to 13 of the phrase have the same pitches, in any octave, but the rhythm differs."),
]
OPERAS = [
    ("Das Rheingold", ["WWV086A"]),
    ("Die Walküre", ["WWV086B-1", "WWV086B-2", "WWV086B-3"]),
    ("Siegfried", ["WWV086C-1", "WWV086C-2", "WWV086C-3"]),
    ("Götterdämmerung", ["WWV086D-0", "WWV086D-1", "WWV086D-2", "WWV086D-3"]),
]
STEP_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PC_NAME = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"]
TIE_GAP = Fraction(1, 32)  # Sibelius rounds the durations of tuplets, so tied notes may miss by a little


def parse_ly(src):
    """Return [(pitch class, duration in quarter notes, MIDI pitch)] for absolute LilyPond notes; ~ merges a tie."""
    notes = []
    for tie, name, octave, den, dots in re.findall(r"(~?)([a-g](?:es|is|s)?)([,']*)(\d+)(\.*)", src):
        midi = 12 * (3 + octave.count("'") - octave.count(",") + 1) + STEP_PC[name[0].upper()] + {"es": -1, "s": -1, "is": 1}.get(name[1:], 0)
        dur = Fraction(4, int(den)) * (2 - Fraction(1, 2 ** len(dots)))
        if tie:
            notes[-1] = (notes[-1][0], notes[-1][1] + dur, notes[-1][2])
        else:
            notes.append((midi % 12, dur, midi))
    return notes


MOTIF = parse_ly(MOTIF_LY)
N = len(MOTIF)


def read_act(path):
    """Return (tied-note-merged notes of both staves, per-measure info, measure start times)."""
    raw, measures = [], []
    for pi, part in enumerate(ET.parse(path).getroot().findall("part")):
        div, fifths, ts, clef = 1, 0, (4, 4), ("G", 2, None)
        for mi, m in enumerate(part.findall("measure")):
            pos = top = start = dur = Fraction(0)
            for e in m:
                if e.tag == "attributes":
                    div = int(e.findtext("divisions") or div)
                    fifths = int(e.findtext("key/fifths") or fifths)
                    if e.find("time") is not None:
                        ts = (int(e.findtext("time/beats")), int(e.findtext("time/beat-type")))
                    if e.find("clef") is not None:
                        clef = (e.findtext("clef/sign"), int(e.findtext("clef/line") or 0), e.findtext("clef/clef-octave-change"))
                elif e.tag in ("backup", "forward"):
                    pos += Fraction(int(e.findtext("duration")), div) * (-1 if e.tag == "backup" else 1)
                elif e.tag == "note" and e.find("grace") is None:
                    if e.find("chord") is None:
                        # A chord note keeps the start and duration of the first note of its chord, because the
                        # export gives some chord notes a <duration> that is shorter than their notated value.
                        start, dur = pos, Fraction(int(e.findtext("duration")), div)
                        pos += dur
                    p = e.find("pitch")
                    if p is not None:
                        step, alter, octave = p.findtext("step"), int(float(p.findtext("alter") or 0)), int(p.findtext("octave"))
                        ties = {t.get("type") for t in e.findall("tie")}
                        raw.append(SimpleNamespace(
                            part=pi, voice=e.findtext("voice") or "1", step=step, alter=alter, octave=octave,
                            midi=12 * (octave + 1) + STEP_PC[step] + alter, mi=mi, pos=start, dur=dur,
                            type=e.findtext("type"), dots=len(e.findall("dot")),
                            tie_start="start" in ties, tie_stop="stop" in ties,
                            el=e, div=div, fifths=fifths, ts=ts, clef=clef))
                top = max(top, pos)
            if pi == 0:
                measures.append(dict(number=int(m.get("number")), nominal=Fraction(ts[0] * 4, ts[1]), fifths=fifths, ts=ts, len=top))
            else:
                measures[mi]["len"] = max(measures[mi]["len"], top)
    offsets, t = [], Fraction(0)
    for m in measures:
        offsets.append(t)
        t += m["len"]
    for p in raw:
        p.onset = offsets[p.mi] + p.pos

    merged, open_ties = [], defaultdict(list)
    for p in sorted(raw, key=lambda p: p.onset):
        waiting = open_ties[(p.part, p.midi)]
        near = [g for g in waiting if abs(g.onset + g.dur - p.onset) <= TIE_GAP] if p.tie_stop else []
        g = next((g for g in near if g.line[1] == p.voice), near[0] if near else None)
        if g:
            g.pieces.append(p)
            g.dur += p.dur
            if not p.tie_start:
                waiting.remove(g)
        else:
            g = SimpleNamespace(pieces=[p], midi=p.midi, onset=p.onset, dur=p.dur, line=(p.part, p.voice))
            merged.append(g)
            if p.tie_start:
                waiting.append(g)
    return merged, measures, offsets


def index(merged):
    """Return the notes by (line, start time) and by (line, end time)."""
    by, ends = defaultdict(list), defaultdict(list)
    for g in merged:
        by[(g.line, g.onset)].append(g)
        ends[(g.line, g.onset + g.dur)].append(g)
    return by, ends


def shape_error(notes, start):
    """Return how far the intervals of `notes` are from the intervals of MOTIF from MOTIF[start]."""
    return sum(abs((b.midi - a.midi) - (MOTIF[start + i + 1][2] - MOTIF[start + i][2])) for i, (a, b) in enumerate(zip(notes, notes[1:])))


def make_run(by, ends, notes, start):
    """Return a passage: `notes` that match MOTIF from MOTIF[start], with the notes of the line before and after them."""
    def nearest(candidates, g):
        return min(candidates, key=lambda c: abs(c.midi - g.midi))

    before, after, cur = [], [], notes[0]
    for _ in range(start):
        if not ends.get((cur.line, cur.onset)):
            break
        cur = nearest(ends[(cur.line, cur.onset)], cur)
        before.insert(0, cur)
    cur = notes[-1]
    for _ in range(min(8, max(3, N - start - len(notes)))):
        if not by.get((cur.line, cur.onset + cur.dur)):
            break
        cur = nearest(by[(cur.line, cur.onset + cur.dur)], cur)
        after.append(cur)
    return SimpleNamespace(length=len(notes), start=start, run=notes, before=before, after=after, shown=before + notes + after)


def apart(spans):
    """Yield the (span, item) pairs of `spans` that do not overlap an earlier pair in time."""
    kept = []
    for (t0, t1), item in spans:
        if not any(t0 < k1 and k0 < t1 for k0, k1 in kept):
            kept.append((t0, t1))
            yield (t0, t1), item


def find_runs(merged, min_len=6):
    """Return the longest partial matches of MOTIF, longest first, without two at the same time.

    A run is a stretch of one line that matches MOTIF[start:start + length] in pitch class and rhythm.
    If a chord doubles the line, the run whose intervals are closest to those of MOTIF_LY wins.
    """
    by, ends = index(merged)

    def extend(line, t, j):
        best = []
        for g in by.get((line, t), ()):
            if g.midi % 12 == MOTIF[j][0] and g.dur == MOTIF[j][1]:
                c = [g] + (extend(line, t + g.dur, j + 1) if j + 1 < N else [])
                if not best or (len(c), -shape_error(c, j)) > (len(best), -shape_error(best, j)):
                    best = c
        return best

    runs = []
    for line, t in by:
        for j in range(N):
            c = extend(line, t, j)
            if len(c) >= min_len:
                runs.append((len(c), j, c))
    runs.sort(key=lambda r: (-r[0], shape_error(r[2], r[1])))
    spans = (((c[0].onset, c[-1].onset + c[-1].dur), (j, c)) for _, j, c in runs)
    return [make_run(by, ends, c, j) for _, (j, c) in apart(spans)]


def find_core(merged):
    """Return the passages in which the notes MOTIF[CORE] have the same pitch classes, with any rhythm."""
    by, ends = index(merged)
    lo, hi = CORE

    def follow(line, t, i):
        for g in by.get((line, t), ()):
            if g.midi % 12 == MOTIF[lo + i][0]:
                if lo + i + 1 == hi:
                    yield [g]
                else:
                    for rest in follow(line, t + g.dur, i + 1):
                        yield [g] + rest

    hits = []
    for line, t in by:
        found = list(follow(line, t, 0))
        if found:
            c = min(found, key=lambda c: shape_error(c, lo))
            hits.append(((c[0].onset, c[-1].onset + c[-1].dur), c))
    return [make_run(by, ends, c, lo) for _, c in apart(sorted(hits, key=lambda h: h[0]))]


def eighths(dur):
    """Return a duration in quarter notes as eighth notes. Sibelius rounds the durations of tuplets, so round them back."""
    return (dur * 2).limit_denominator(12)


def describe(pc, dur):
    return f"{PC_NAME[pc]} of {eighths(dur)} eighth note{'' if eighths(dur) == 1 else 's'}"


def difference(run):
    """Return the text that tells how a partial match differs from MOTIF_LY."""
    j, end = run.start, run.start + run.length
    text = [f"Your notes {j + 1} to {end} (of {N}) match in pitch and rhythm."]
    if j > 0:
        text.append(f"Before them, the score has {describe(run.before[-1].midi % 12, run.before[-1].dur)}; yours has {describe(*MOTIF[j - 1][:2])}."
                    if run.before else "Before them, the line of the score starts.")
    if end < N:
        text.append(f"After them, the score has {describe(run.after[0].midi % 12, run.after[0].dur)}; yours has {describe(*MOTIF[end][:2])}."
                    if run.after else "After them, the line of the score ends.")
    return " ".join(text)


def rhythm_difference(run):
    """Return the text that tells how the rhythm of a core match differs from MOTIF_LY."""
    def row(durations):
        return " ".join(str(eighths(d)) for d in durations)
    return (f"Your notes {run.start + 1} to {run.start + run.length} (of {N}) have the same pitches here, but not the same rhythm. "
            f"In eighth notes, the score plays them as {row(g.dur for g in run.run)}; yours are "
            f"{row(m[1] for m in MOTIF[run.start:run.start + run.length])}.")


def trim_spans(notes):
    """Remove the beams, slurs and tuplet brackets that the cut leaves without a start or an end."""
    bad, group = [], []
    for n in notes:
        beam = n.findtext("beam")
        if beam == "begin":
            bad += group
            group = [n]
        elif beam in ("continue", "end") and group:
            group.append(n)
            if beam == "end":
                group = []
        else:
            bad += group + ([n] if beam else [])
            group = []
    for n in bad + group:
        for b in n.findall("beam"):
            n.remove(b)
    for tag in ("slur", "tuplet"):
        spans = [(parent, s) for n in notes for parent in n.findall("notations") for s in parent.findall(tag)]
        open_, keep = {}, set()
        for _, s in spans:
            key = s.get("number", "1")
            if s.get("type") == "start":
                open_[key] = s
            elif s.get("type") == "stop" and key in open_:
                keep |= {id(open_.pop(key)), id(s)}
        for parent, s in spans:
            if id(s) not in keep:
                parent.remove(s)


def excerpt(chain, measures):
    """Return a MusicXML score of the source notes of one match.

    The notes are copies of the notes in the score, so the clef, key, time signature, octave, rhythm,
    accidentals, stems, beams and ties are the ones of the score. Other notes and rests are left out.
    """
    pieces = sorted((p for g in chain for p in g.pieces), key=lambda p: p.onset)
    notes = []
    for p in pieces:
        n = copy.deepcopy(p.el)
        n.attrib.clear()
        for tag in ("chord", "instrument", "lyric"):
            for x in n.findall(tag):
                n.remove(x)
        notes.append(n)
    trim_spans(notes)

    part, last, mi = ET.Element("part", id="P1"), None, None
    for p, n in zip(pieces, notes):
        if p.mi != mi:
            mi = p.mi
            m = ET.SubElement(part, "measure", number=str(measures[mi]["number"]))
            if last is None and p.pos > 0:
                m.set("implicit", "yes")  # the match starts with a pickup
        now = dict(divisions=p.div, key=p.fifths, time=p.ts, clef=p.clef)
        changed = {k for k in now if last is None or now[k] != last[k]}
        if changed:
            a = ET.SubElement(m, "attributes")
            if "divisions" in changed:
                ET.SubElement(a, "divisions").text = str(p.div)
            if "key" in changed:
                ET.SubElement(ET.SubElement(a, "key"), "fifths").text = str(p.fifths)
            if "time" in changed:
                t = ET.SubElement(a, "time")
                for tag, value in zip(("beats", "beat-type"), p.ts):
                    ET.SubElement(t, tag).text = str(value)
            if "clef" in changed:
                c = ET.SubElement(a, "clef")
                ET.SubElement(c, "sign").text = p.clef[0]
                if p.clef[1]:
                    ET.SubElement(c, "line").text = str(p.clef[1])
                if p.clef[2]:
                    ET.SubElement(c, "clef-octave-change").text = p.clef[2]
        m.append(n)
        last = now

    root = ET.Element("score-partwise", version="3.0")
    ET.SubElement(ET.SubElement(ET.SubElement(root, "part-list"), "score-part", id="P1"), "part-name")
    root.append(part)
    for e in root.iter():  # drop the indentation that the copied notes carry
        e.tail = None
        if e.text and not e.text.strip():
            e.text = None
    return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(root, encoding="unicode")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", type=pathlib.Path, default=ROOT / "data")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "leitmotifs" / "motifs" / f"{MOTIF_ID}.json")
    ap.add_argument("--closest", type=int, default=2, help="partial matches of the whole phrase that make level 1, if none is complete")
    args = ap.parse_args()
    ann, score = args.data / "02_Annotations", args.data / "01_RawData" / "score_musicxml"

    sections, runs, cores = [], [], []
    for opera, works in OPERAS:
        for work in works:
            scenes = [(float(r["measure_start"]), float(r["measure_end"]), int(r["scene"])) for r in read_csv(f"{ann}/ann_score_scenes/Wagner_{work}.csv")]
            end = math.floor(scenes[-1][1]) + 1
            if work == "WWV086A":  # one act, so each scene becomes a section
                for i, (start, _, sc) in enumerate(scenes):
                    sections.append(dict(id=f"A-{sc}", opera=opera, act=work, label=f"Scene {sc}", short=f"Sc {sc}",
                                         **{"from": start, "to": scenes[i + 1][0] if i + 1 < len(scenes) else end}))
            else:
                sections.append(dict(id=work[6:], opera=opera, act=work, label="Prologue" if work == "WWV086D-0" else f"Act {work[-1]}",
                                     **({"short": "Pro"} if work == "WWV086D-0" else {}), **{"from": scenes[0][0], "to": end}))

            merged, measures, offsets = read_act(score / f"Wagner_{work}.xml")
            singing = [(float(r["measure_start"]), float(r["measure_end"]), r["person"], r["text"])
                       for r in read_csv(f"{ann}/ann_score_singing/Wagner_{work}.csv")]
            act = SimpleNamespace(work=work, scenes=scenes, singing=singing, measures=measures, offsets=offsets)
            runs += [(run, act) for run in find_runs(merged)]
            cores += [(run, act) for run in find_core(merged)]

    def span(run, act):
        return act.work, run.shown[0].onset, run.shown[-1].onset + run.shown[-1].dur

    level1 = [f for f in runs if f[0].length == N] or sorted(runs, key=lambda f: -f[0].length)[:args.closest]
    taken = [span(*f) for f in level1]
    level2 = [f for f in cores if not any(w == span(*f)[0] and span(*f)[1] < t1 and t0 < span(*f)[2] for w, t0, t1 in taken)]

    translations_path = ROOT / "leitmotifs" / "translations.json"
    translations = json.loads(translations_path.read_text(encoding="utf-8")) if translations_path.exists() else {}
    untranslated = set()

    occurrences = []
    for level, found in ((1, level1), (2, level2)):
        for run, act in found:
            def locate(t):
                mi = bisect_right(act.offsets, t) - 1
                return act.measures[mi]["number"] + round(float((t - act.offsets[mi]) / act.measures[mi]["nominal"]), 3)

            a, b = locate(run.shown[0].onset), locate(run.shown[-1].onset + run.shown[-1].dur)
            same_rhythm = all(g.dur == m[1] for g, m in zip(run.run, MOTIF[run.start:]))
            if level == 1:
                label = "Exact match" if run.length == N else f"Closest match: {run.length} of {N} notes"
                note = None if run.length == N else difference(run)
            else:
                label = "Same pitches and rhythm" if same_rhythm else "Same pitches, different rhythm"
                note = None if same_rhythm else rhythm_difference(run)
            occurrences.append(dict(
                id=f"{act.work[6:]}-{a:.3f}", act=act.work, level=level,
                scene=next((sc for s, e, sc in act.scenes if s <= a <= e + 0.001), None), label=label, note=note,
                libretto=[dict(kind="sung", person=p, text=x, **({"translation": translations[x]} if x in translations else {}))
                          for s, e, p, x in act.singing if s < b and e >= a],
                notation=dict(musicxml=excerpt(run.shown, act.measures)), **{"from": a, "to": b}))
            untranslated |= {l["text"] for l in occurrences[-1]["libretto"] if "translation" not in l}
            print(f"level {level}  {act.work:10s} measure {a:9.3f}  {label}")
    order = {s["act"]: i for i, s in enumerate(sections)}
    occurrences.sort(key=lambda o: (order[o["act"]], o["from"]))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(dict(format=1, motif=dict(id=MOTIF_ID, name=MOTIF_NAME,
                                            description="Passages of the piano score that match one melody, in levels by how close they are to it. Level 1 is the closest."),
                       levels=LEVELS, sections=sections, occurrences=occurrences), f, ensure_ascii=False, indent=1)
    print(f"{len(occurrences)} occurrences written to {args.out}")
    for text in sorted(untranslated):
        print(f"no English in {translations_path.name} for: {text}")


if __name__ == "__main__":
    main()
