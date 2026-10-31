"""Find a melody in the piano score of the Wagner Ring Dataset and write the motif data
file that leitmotifs/index.html reads (format: leitmotifs/DATA-SPEC.md).

The melody comes from a definition file, leitmotifs/definitions/<id>.json, so that the same searches serve
every leitmotif. The file holds: id, name, lilypond (the melody in absolute LilyPond notes), core_notes (the first
and last note, counted from 1, that levels 2 and 3 look for) and original (octaves_up, time and partial: how the
page draws the melody).

Each passage has a level that tells how close it is to the melody (see levels()). All notes of a
passage are in one staff and voice, they follow each other with no gap, and tied notes are merged.
Passages may overlap in time. Two passages count as one only if they are the same statement: they end on the same
note of the same staff and voice, or they begin and end at the same moments.
The notation excerpt of a passage is copied from the score (see excerpt()).

usage: python3 -I tools/find_motif.py MOTIF_ID [--data DIR] [--out FILE] [--closest N]
"""
import argparse, copy, csv, json, math, pathlib, re, subprocess, tempfile
import xml.etree.ElementTree as ET
from bisect import bisect_right
from collections import defaultdict
from fractions import Fraction
from itertools import islice
from types import SimpleNamespace

MAX_CHAINS = 64  # the most ways to match one start that find_core() compares
ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFINITIONS = ROOT / "leitmotifs" / "definitions"
ORIGINAL_ACT = "ORIGINAL"  # the act id of the original melody, which is not part of the score


def openings():
    """Return how many notes the levels after "Other keys" keep: the first notes of the core, longest first.
    The count is in notes of MOTIF, which has repeated notes merged. A definition may set "openings"."""
    return [k for k in DEF.get("openings", [8, 6]) if k < CORE[1] - CORE[0]]


def levels():
    """Return the description of each level, for the motif file."""
    first, last = DEF["core_notes"]
    chance = "Short cells also match by chance, so some of these passages are coincidences."
    out = [
        dict(level=0, label="Original", name="The melody as given",
             description="The melody as you gave it. It is not a passage of the score."),
        dict(level=1, name="Closest to the original",
             description="The best partial matches of the whole phrase. The pitches and the rhythm are the same, in any octave."),
        dict(level=2, name="Same core pitches",
             description=f"Notes {first} to {last} of the phrase have the same pitches, in any octave, but the rhythm differs."),
        dict(level=3, name="One note different",
             description=f"Notes {first} to {last} of the phrase have the same pitches, in any octave, except one note. The rhythm may differ."),
        dict(level=4, name="Other keys",
             description=f"Notes {first} to {last} of the phrase have the same intervals, moved to another key, in any octave. The rhythm may differ."),
    ]
    for level, k in enumerate(openings(), start=5):
        a, b = numbers(CORE[0], k)
        out.append(dict(level=level, name=f"Opening, other keys" if level == 5 else "Shorter opening, other keys",
                        description=f"Only the first notes, {a} to {b} of the phrase, have the same intervals, moved to another key. The rhythm may differ. {chance}"))
    return out


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


def collapse(notes):
    """Merge a run of notes that repeat one pitch into one note, and add the first and last index of its notes."""
    out = []
    for i, (pc, dur, midi) in enumerate(notes):
        if out and out[-1][2] == midi:
            out[-1] = (pc, out[-1][1] + dur, midi, out[-1][3], i)
        else:
            out.append((pc, dur, midi, i, i))
    return out


DEF = IDEAL = MOTIF = N = CORE = None  # set by use()


def load_definition(motif_id):
    return json.loads((DEFINITIONS / f"{motif_id}.json").read_text(encoding="utf-8"))


def use(definition):
    """Make `definition` the melody that every search in this module looks for."""
    global DEF, IDEAL, MOTIF, N, CORE
    DEF, IDEAL = definition, parse_ly(definition["lilypond"])
    MOTIF = collapse(IDEAL)  # what the search matches: a repeated note counts as one note
    N = len(MOTIF)
    CORE = tuple(next(i for i, m in enumerate(MOTIF) if m[3] <= n - 1 <= m[4]) + k for n, k in zip(definition["core_notes"], (0, 1)))


def numbers(start, length):
    """Return the numbers (counted from 1) of the first and last note of the melody in MOTIF[start:start + length]."""
    return MOTIF[start][3] + 1, MOTIF[start + length - 1][4] + 1


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
    """Return the notes by (line, start time) and by (line, end time).

    A few notes of the score have no duration. They are left out, because a note without duration
    would be its own next repeat.
    """
    by, ends = defaultdict(list), defaultdict(list)
    for g in merged:
        if g.dur <= 0:
            continue
        by[(g.line, g.onset)].append(g)
        ends[(g.line, g.onset + g.dur)].append(g)
    return by, ends


def shape_error(groups, start):
    """Return how far the intervals of the `groups` are from the intervals of MOTIF from MOTIF[start]."""
    return sum(abs((b[0].midi - a[0].midi) - (MOTIF[start + i + 1][2] - MOTIF[start + i][2])) for i, (a, b) in enumerate(zip(groups, groups[1:])))


def repeats(by, g):
    """Yield [g], then [g, next repeat of its pitch], and so on. A repeat starts when the note before it ends."""
    group = [g]
    while True:
        yield list(group)
        again = [h for h in by.get((g.line, group[-1].onset + group[-1].dur), ()) if h.midi == g.midi]
        if not again:
            return
        group.append(again[0])


def total(group):
    return sum(n.dur for n in group)


def make_run(by, ends, groups, start):
    """Return a passage: `groups` of notes that match MOTIF from MOTIF[start], with the groups of the line before and after."""
    def nearest(candidates, g):
        return min(candidates, key=lambda c: abs(c.midi - g.midi))

    # The notes around the passage are only context. Each one is a group of its own, so a held chord note
    # of the same pitch cannot turn them into a long run.
    before, after, cur = [], [], groups[0][0]
    for _ in range(start):
        if not ends.get((cur.line, cur.onset)):
            break
        cur = nearest(ends[(cur.line, cur.onset)], cur)
        before.insert(0, [cur])
    cur = groups[-1][-1]
    for _ in range(min(8, max(3, N - start - len(groups)))):
        if not by.get((cur.line, cur.onset + cur.dur)):
            break
        cur = nearest(by[(cur.line, cur.onset + cur.dur)], cur)
        after.append([cur])
    notes = [n for g in groups for n in g]
    flat = lambda gs: [n for g in gs for n in g]
    return SimpleNamespace(length=len(groups), start=start, groups=groups, run=notes, before=before, after=after,
                           shown=flat(before) + notes + flat(after))


def identity(run):
    """Return the keys by which two passages are the same statement: where it ends in its line, where it starts in
    its line (a shorter cell that begins with a longer passage is part of it), and its start and end."""
    last, first = run.groups[-1][-1], run.groups[0][0]
    end = last.onset + last.dur
    return ("end", first.line, end), ("start", first.line, first.onset), ("span", first.onset, end)


def find_runs(merged, min_len=6):
    """Return the longest partial matches of MOTIF, longest first.

    A run is a stretch of one line that matches MOTIF[start:start + length] in pitch class and rhythm.
    Runs may overlap in time. A shorter run is dropped only if a longer one has the same alignment with MOTIF,
    which means that it is a part of the same statement.
    Notes that repeat one pitch in a row count as one note: a group of repeats matches a note of MOTIF if
    the durations of the group add up to the duration of that note.
    If a chord doubles the line, the run whose intervals are closest to those of the melody wins.
    """
    by, ends = index(merged)

    def extend(line, t, j):
        best = []
        for g in by.get((line, t), ()):
            if g.midi % 12 != MOTIF[j][0]:
                continue
            for group in repeats(by, g):
                if total(group) > MOTIF[j][1]:
                    break
                if total(group) == MOTIF[j][1]:
                    c = [group] + (extend(line, t + total(group), j + 1) if j + 1 < N else [])
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
    seen, kept = set(), []
    for _, j, c in runs:
        phrase_start = c[0][0].onset - sum(m[1] for m in MOTIF[:j])  # where MOTIF would begin, if this run were its start
        if phrase_start not in seen:
            seen.add(phrase_start)
            kept.append(make_run(by, ends, c, j))
    return kept


def find_core(merged, transposed=False, wrong=0, length=None):
    """Return the passages in which the notes MOTIF[CORE] have the same pitch classes, with any rhythm.

    If `transposed` is true, the passages have the same intervals instead, so the key may differ.
    `wrong` notes may be anything. `length` keeps only the first `length` notes of the core.
    Notes that repeat one pitch in a row count as one note.
    """
    by, ends = index(merged)
    lo = CORE[0]
    hi = CORE[1] if length is None else lo + length

    def follow(line, t, i, prev, errors, allowed):
        for g in by.get((line, t), ()):
            pc, before = MOTIF[lo + i][0], MOTIF[lo + i - 1][0]
            right = (g.midi % 12 == pc) if not transposed else (i == 0 or (g.midi - prev.midi) % 12 == (pc - before) % 12)
            if errors + (not right) > allowed:
                continue
            # Try every number of repeats, because a held chord note of the same pitch can run on after the melody.
            for group in repeats(by, g):
                if lo + i + 1 == hi:
                    yield [group]
                else:
                    for rest in follow(line, group[-1].onset + group[-1].dur, i + 1, g, errors + (not right), allowed):
                        yield [group] + rest

    # Passages may overlap. Starts at the repeats of the first note give the same statement, and so does
    # the same statement in two staves, so each statement is kept once, at its earliest start.
    best = {}
    for line, t in by:
        for allowed in range(wrong + 1):  # a start that has an exact match needs no wrong note
            # Each wrong note multiplies the ways to match, so look at a limited number of them only.
            found = list(islice(follow(line, t, 0, None, 0, allowed), MAX_CHAINS))
            if found:
                break
        if found:
            c = min(found, key=lambda c: (shape_error(c, lo), -len(c[0])))
            span = (c[0][0].onset, c[-1][-1].onset + c[-1][-1].dur)
            if (line, span[1]) not in best or span[0] < best[(line, span[1])][0][0]:
                best[(line, span[1])] = (span, c)
    return [make_run(by, ends, c, lo) for _, c in sorted({span: (span, c) for span, c in best.values()}.values(), key=lambda h: h[0])]


def eighths(dur):
    """Return a duration in quarter notes as eighth notes. Sibelius rounds the durations of tuplets, so round them back."""
    return (dur * 2).limit_denominator(12)


def describe(pc, dur):
    return f"{PC_NAME[pc]} of {eighths(dur)} eighth note{'' if eighths(dur) == 1 else 's'}"


def difference(run):
    """Return the text that tells how a partial match differs from the melody."""
    j, end = run.start, run.start + run.length
    text = [f"Your notes {numbers(j, run.length)[0]} to {numbers(j, run.length)[1]} (of {len(IDEAL)}) match in pitch and rhythm."]
    if j > 0:
        text.append(f"Before them, the score has {describe(run.before[-1][0].midi % 12, total(run.before[-1]))}; yours has {describe(*MOTIF[j - 1][:2])}."
                    if run.before else "Before them, the line of the score starts.")
    if end < N:
        text.append(f"After them, the score has {describe(run.after[0][0].midi % 12, total(run.after[0]))}; yours has {describe(*MOTIF[end][:2])}."
                    if run.after else "After them, the line of the score ends.")
    return " ".join(text)


def rhythm_text(run):
    """Return the text that tells the rhythm of a core match next to the rhythm of the melody."""
    def row(durations):
        return " ".join(str(eighths(d)) for d in durations)
    return (f"In eighth notes, the score plays them as {row(total(g) for g in run.groups)}; yours are "
            f"{row(m[1] for m in MOTIF[run.start:run.start + run.length])}.")


def rhythm_difference(run):
    """Return the text that tells how the rhythm of a same-pitch core match differs from the melody."""
    first, last = numbers(run.start, run.length)
    return f"Your notes {first} to {last} (of {len(IDEAL)}) have the same pitches here, but not the same rhythm. {rhythm_text(run)}"


def wrong_note_difference(run, same_rhythm):
    """Return the text that tells which note of a one-note-different core match is not the one of the melody."""
    first, last = numbers(run.start, run.length)
    parts = []
    for k, group in enumerate(run.groups, start=run.start):
        if group[0].midi % 12 != MOTIF[k][0]:
            a, b = MOTIF[k][3] + 1, MOTIF[k][4] + 1
            parts.append(f"Your note{'' if a == b else 's'} {a if a == b else f'{a} to {b}'} {'is' if a == b else 'are'} "
                         f"{PC_NAME[MOTIF[k][0]]}; the score has {PC_NAME[group[0].midi % 12]} there.")
    return (f"Your notes {first} to {last} (of {len(IDEAL)}) have the same pitches here, except one. {' '.join(parts)} "
            + ("The rhythm is the same." if same_rhythm else f"The rhythm differs. {rhythm_text(run)}"))


def key_difference(run, same_rhythm):
    """Return the text that tells how a transposed core match differs from the melody."""
    mine, here = MOTIF[run.start][0], run.run[0].midi % 12
    up = (here - mine) % 12
    first, last = numbers(run.start, run.length)
    return (f"Your notes {first} to {last} (of {len(IDEAL)}) have the same intervals here, in another key: "
            f"your {PC_NAME[mine]} becomes {PC_NAME[here]}, which is {up} semitone{'' if up == 1 else 's'} up or {12 - up} down. "
            + ("The rhythm is the same." if same_rhythm else f"The rhythm differs. {rhythm_text(run)}"))


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


def original_musicxml():
    """Return a MusicXML score of the melody that the page only uses to play it.

    It has the pitches and durations of the melody and the ties that it marks. The score looks like nothing:
    it uses LilyPond's default clef, key and 4/4, and splits a note that crosses a barline into tied notes.
    The drawing of the original comes from original_svg().
    """
    bar = 8  # eighth notes in 4/4
    kinds = {8: ("whole", 0), 6: ("half", 1), 4: ("half", 0), 3: ("quarter", 1), 2: ("quarter", 0), 1: ("eighth", 0)}
    tokens = re.findall(r"(~?)([a-g](?:es|is|s)?)([,']*)(\d+)(\.*)", DEF["lilypond"])
    notes, pos = [], 0
    for i, (tie, name, octave, den, dots) in enumerate(tokens):
        pitch = (name[0].upper(), {"es": -1, "s": -1, "is": 1}.get(name[1:], 0),
                 3 + octave.count("'") - octave.count(",") + DEF["original"]["octaves_up"])
        tied_on = i + 1 < len(tokens) and bool(tokens[i + 1][0])
        remaining, pieces = int(Fraction(8, int(den)) * (2 - Fraction(1, 2 ** len(dots)))), []
        while remaining:
            room = min(remaining, bar - pos % bar)  # up to the next barline
            while room:
                part = next(v for v in kinds if v <= room)  # the longest note value that fits
                pieces.append((part, pos))
                room, remaining, pos = room - part, remaining - part, pos + part
        for k, (part, at) in enumerate(pieces):
            notes.append(dict(pitch=pitch, eighths=part, bar=at // bar, tie_stop=bool(tie) if k == 0 else True,
                              tie_start=True if k < len(pieces) - 1 else tied_on))
    measures = defaultdict(str)
    for n in notes:
        step, alter, octave = n["pitch"]
        kind, dots = kinds[n["eighths"]]
        measures[n["bar"]] += (f"<note><pitch><step>{step}</step>{f'<alter>{alter}</alter>' if alter else ''}<octave>{octave}</octave></pitch>"
                               f"<duration>{n['eighths']}</duration>" + '<tie type="stop"/>' * n["tie_stop"] + '<tie type="start"/>' * n["tie_start"]
                               + f"<voice>1</voice><type>{kind}</type>" + "<dot/>" * dots
                               + ("<notations>" + '<tied type="stop"/>' * n["tie_stop"] + '<tied type="start"/>' * n["tie_start"] + "</notations>"
                                  if n["tie_stop"] or n["tie_start"] else "") + "</note>")
    attributes = "<attributes><divisions>2</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>"
    body = "".join(f'<measure number="{b + 1}">{attributes if b == 0 else ""}{xml}</measure>' for b, xml in sorted(measures.items()))
    return ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.0"><part-list><score-part id="P1"><part-name/></score-part></part-list>'
            f'<part id="P1">{body}</part></score-partwise>')


def original_svg():
    """Return the SVG that LilyPond draws for the melody exactly as written.

    The LilyPond file holds the notes of the melody, its pickup (\\partial) and its time, which the definition gives
    (the durations of the melody fill the bars only in that time). LilyPond uses its own clef and key.
    \\transpose moves the notes up `octaves_up` octaves and leaves the text of the melody as it is.
    It only adds what a tight, cropped drawing needs: no indent, no page number and no tagline.
    LilyPond runs in the Docker image of the project notes. If it cannot run, this raises an error. The original
    must never be drawn by anything else.
    """
    original = DEF["original"]
    source = ('\\version "2.25.12"\n'
              "\\paper { indent = 0\\mm print-page-number = ##f oddHeaderMarkup = ##f evenHeaderMarkup = ##f "
              "oddFooterMarkup = ##f evenFooterMarkup = ##f tagline = ##f }\n"
              "\\transpose c c" + "'" * original["octaves_up"] + f" {{ \\time {original['time']} \\partial {original['partial']} "
              + DEF["lilypond"] + " }\n")
    with tempfile.TemporaryDirectory() as tmp:
        pathlib.Path(tmp, "original.ly").write_text(source, encoding="utf-8")
        command = ["docker", "run", "--rm", "-v", f"{tmp}:/app", "-w", "/app", "jeandeaual/lilypond:latest",
                   "lilypond", "-dbackend=svg", "-dcrop", "-dno-point-and-click", "original.ly"]
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(f"LilyPond did not run ({error}). The command was: {' '.join(command)}") from error
        drawing = pathlib.Path(tmp, "original.cropped.svg")
        if done.returncode or not drawing.exists():
            raise RuntimeError(f"LilyPond failed with exit code {done.returncode}: {done.stderr[-600:]}")
        svg = drawing.read_text(encoding="utf-8")
    svg = svg[svg.index("<svg"):].strip()  # drop any XML declaration before the root element
    for forbidden in ("<script", "href", "url("):
        if forbidden in svg:
            raise RuntimeError(f"The drawing of LilyPond holds '{forbidden}', which the page must not load.")
    return svg


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("motif", help="the id of a definition in leitmotifs/definitions, for example siegfried")
    ap.add_argument("--data", type=pathlib.Path, default=ROOT / "data")
    ap.add_argument("--out", type=pathlib.Path, help="default: leitmotifs/motifs/<id>.json")
    ap.add_argument("--closest", type=int, default=2, help="partial matches of the whole phrase that make level 1, if none is complete")
    ap.add_argument("--refresh", action="store_true",
                    help="only refresh the texts of the existing output file, which are the translations and the level descriptions, without the search (a few seconds)")
    args = ap.parse_args()
    use(load_definition(args.motif))
    args.out = args.out or ROOT / "leitmotifs" / "motifs" / f"{DEF['id']}.json"
    if args.refresh:
        translations = json.loads((ROOT / "leitmotifs" / "translations.json").read_text(encoding="utf-8"))
        data = json.loads(args.out.read_text(encoding="utf-8"))
        missing = set()
        for o in data["occurrences"]:
            for line in o["libretto"] or []:
                if line["kind"] == "sung":
                    line.pop("translation", None)
                    if line["text"] in translations:
                        line["translation"] = translations[line["text"]]
                    else:
                        missing.add(line["text"])
        data["levels"] = levels()
        args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"texts refreshed in {args.out}")
        for text in sorted(missing):
            print(f"no English in translations.json for: {text}")
        return
    ann, score = args.data / "02_Annotations", args.data / "01_RawData" / "score_musicxml"

    sections, runs, cores, wrongs, keys = [], [], [], [], []
    shorts = {k: [] for k in openings()}
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
            wrongs += [(run, act) for run in find_core(merged, wrong=1)]
            keys += [(run, act) for run in find_core(merged, transposed=True)]
            for k in shorts:
                shorts[k] += [(run, act) for run in find_core(merged, transposed=True, length=k)]

    def new_in(found, taken):
        """Return the passages of `found` that are not the same statement as one in `taken`, and add them to `taken`.
        A passage that only overlaps one in `taken` in time is a different statement and stays."""
        fresh = []
        for run, act in found:
            keys_of = [(act.work, k) for k in identity(run)]
            if not any(k in taken for k in keys_of):
                fresh.append((run, act))
                taken.update(keys_of)
        return fresh

    taken = set()
    level1 = [f for f in runs if f[0].length == N] or sorted(runs, key=lambda f: -f[0].length)[:args.closest]
    for run, act in level1:
        taken.update((act.work, k) for k in identity(run))
    found_at = {1: level1, 2: new_in(cores, taken), 3: new_in(wrongs, taken), 4: new_in(keys, taken)}
    for level, k in enumerate(openings(), start=5):  # the shorter the cell, the later the level
        found_at[level] = new_in(shorts[k], taken)

    translations_path = ROOT / "leitmotifs" / "translations.json"
    translations = json.loads(translations_path.read_text(encoding="utf-8")) if translations_path.exists() else {}
    untranslated = set()

    occurrences = []
    for level, found in sorted(found_at.items()):
        for run, act in found:
            def locate(t):
                mi = bisect_right(act.offsets, t) - 1
                return act.measures[mi]["number"] + round(float((t - act.offsets[mi]) / act.measures[mi]["nominal"]), 3)

            a, b = locate(run.shown[0].onset), locate(run.shown[-1].onset + run.shown[-1].dur)
            same_rhythm = all(total(g) == m[1] for g, m in zip(run.groups, MOTIF[run.start:]))
            if level == 1:
                first, last = numbers(run.start, run.length)
                label = "Exact match" if run.length == N else f"Closest match: {last - first + 1} of {len(IDEAL)} notes"
                note = None if run.length == N else difference(run)
            elif level == 2:
                label = "Same pitches and rhythm" if same_rhythm else "Same pitches, different rhythm"
                note = None if same_rhythm else rhythm_difference(run)
            elif level == 3:
                label = "Same pitches, one note different"
                note = wrong_note_difference(run, same_rhythm)
            elif level == 4:
                label = "Another key, same rhythm" if same_rhythm else "Another key, different rhythm"
                note = key_difference(run, same_rhythm)
            else:
                first, last = numbers(run.start, run.length)
                label = f"First {last - first + 1} notes, another key"
                note = key_difference(run, same_rhythm)
            unique = f"{act.work[6:]}-{a:.3f}"
            while unique in {o["id"] for o in occurrences}:  # overlapping passages may begin at the same note
                unique += f"-L{level}"
            occurrences.append(dict(
                id=unique, act=act.work, level=level,
                scene=next((sc for s, e, sc in act.scenes if s <= a <= e + 0.001), None), label=label, note=note,
                libretto=[dict(kind="sung", person=p, text=x, **({"translation": translations[x]} if x in translations else {}))
                          for s, e, p, x in act.singing if s < b and e >= a],
                notation=dict(musicxml=excerpt(run.shown, act.measures)), **{"from": a, "to": b}))
            untranslated |= {l["text"] for l in occurrences[-1]["libretto"] if "translation" not in l}
            print(f"level {level}  {act.work:10s} measure {a:9.3f}  {label}")
    # The original melody comes first. Its short section sits to the left of the start of Das Rheingold.
    width = round(sum(s["to"] - s["from"] for s in sections) * 0.04)
    sections.insert(0, dict(id="original", opera="", act=ORIGINAL_ACT, label="Original", short="Orig", original=True, **{"from": 0, "to": width}))
    up, words = DEF["original"]["octaves_up"], {1: "one", 2: "two", 3: "three"}
    pickups = {"2": "one half note", "4": "one quarter note", "8": "one eighth note", "16": "one sixteenth note"}
    occurrences.append(dict(
        id="original", act=ORIGINAL_ACT, level=0, scene=None, label="The original",
        note=(f"The melody as you gave it, {words.get(up, up)} octave{'' if up == 1 else 's'} higher, " if up else "The melody as you gave it, ")
             + f"drawn by LilyPond from your notes. The first note is a pickup of {pickups.get(DEF['original']['partial'], DEF['original']['partial'])}, "
             f"the bars are in {DEF['original']['time']}, and the clef and key are LilyPond's own. It is not a passage of the score.",
        libretto=None, notation=dict(svg=original_svg(), musicxml=original_musicxml()), **{"from": width / 2, "to": width / 2 + 1}))
    order = {s["act"]: i for i, s in enumerate(sections)}
    occurrences.sort(key=lambda o: (order[o["act"]], o["from"]))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(dict(format=1, motif=dict(id=DEF["id"], name=DEF["name"],
                                            description="Passages of the piano score that match one melody, in levels by how close they are to it. Level 1 is the closest. A run of repeated notes counts as one note."),
                       levels=levels(), sections=sections, occurrences=occurrences), f, ensure_ascii=False, indent=1)
    print(f"{len(occurrences)} occurrences written to {args.out}")
    for text in sorted(untranslated):
        print(f"no English in {translations_path.name} for: {text}")


if __name__ == "__main__":
    main()
