"""Find a melody in the piano score of the Wagner Ring Dataset and write the motif data
file that leitmotifs/index.html reads (format: leitmotifs/DATA-SPEC.md).

The melody comes from a definition file, leitmotifs/definitions/<id>.json, so that the same searches serve
every leitmotif. The file holds: id, name, lilypond (the melody in absolute LilyPond notes), core_notes (the first
and last note, counted from 1, that levels 2 and 3 look for) and original (octaves_up, time and partial: how the
page draws the melody; partial, clef and key_signature are optional, see original_musicxml()). It may also set
openings (see openings()), max_level (the farthest level to look for), source (a key of leitmotifs/sources.json) and variant (the
letter of one form of a leitmotif that has several: the page lists the forms under one heading, see full_name()) and place
({act, from, to, label, note}: for a leitmotif that is no melody, such as the held E-flat of the Beginning, there is no search; its one passage is
the measures from `from` to `to` of `act`, see placed_run()). The melody may have rests, tuplets and 32nd
notes (see ly_tokens()); a note that is not a pitch, a rest or a tuplet is an error.

Each passage has a level that tells how close it is to the melody (see levels()). All notes of a
passage are in one staff and voice, they follow each other with no gap, and tied notes are merged. A rest of the
melody is a gap of that length: level 1 needs the same rest in the score, the other levels also accept none.
Two notes that follow each other cannot start in the same chord: a chord that repeats is not a melody.
Passages may overlap in time. Two passages count as one only if they are the same statement: they end on the same
note of the same staff and voice, or they begin and end at the same moments.
The voice of the score has no staff of its own: it is part of a piano staff. So in a sung passage (the singing annotations) a level 2
passage may skip one short note of its line, which the piano plays and the voice does not sing (see find_core()).
The notation excerpt of a passage is copied from the score (see excerpt()). It carries the tempo of one recording
(see PERFORMANCE), so that the sound of the page plays at the speed of a performance. The whole piano score of the same
measures goes to a second file, <id>.full.json (see full_excerpt()).
The passages of one act that overlap, or lie within MERGE_GAP measures of each other, are written as one example, also if they are
in different staves or voices (see join_overlapping() and join_runs()).

usage: python3 -I tools/find_motif.py MOTIF_ID [--data DIR] [--out FILE] [--closest N]
"""
import argparse, copy, csv, json, math, pathlib, re, unicodedata
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
MERGE_GAP = 1  # passages that overlap, or lie within this many measures of each other, are one example
PERFORMANCE = "Karajan1966"  # the recording whose measure times set the tempo of the sound (one of the three with hand-made times)


def openings():
    """Return how many notes the levels after "Other keys" keep: the first notes of the core, longest first.
    The count is in notes of MOTIF, which has repeated notes merged. A definition may set "openings"."""
    return [k for k in DEF.get("openings", [8, 6]) if k < CORE[1] - CORE[0]] if DEF.get("max_level", 9) >= 5 else []


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
             description=f"Notes {first} to {last} of the phrase have the same pitches, in any octave, but the rhythm differs. "
                         "In a sung passage the score may have one short extra note between two of them: it is skipped."),
        dict(level=3, name="One note different",
             description=f"Notes {first} to {last} of the phrase have the same pitches, in any octave, except one note. The rhythm may differ."),
        dict(level=4, name="Other keys",
             description=f"Notes {first} to {last} of the phrase have the same intervals, moved to another key, in any octave. The rhythm may differ."),
    ]
    for level, k in enumerate(openings(), start=5):
        a, b = numbers(CORE[0], k)
        out.append(dict(level=level, name=f"Opening, other keys" if level == 5 else "Shorter opening, other keys",
                        description=f"Only the first notes, {a} to {b} of the phrase, have the same intervals, moved to another key. The rhythm may differ. {chance}",
                        **({"hidden_by_default": True} if level == 4 + len(openings()) else {})))  # the shortest opening is mostly chance
    if "place" in DEF:
        out = out[:1] + [dict(level=1, name="Placed by hand",
                              description="This leitmotif is not a melody that a search can find. Its place in the score was set by hand.")]
    return [l for l in out if l["level"] <= DEF.get("max_level", 9)]


OPERAS = [
    ("Das Rheingold", ["WWV086A"]),
    ("Die Walküre", ["WWV086B-1", "WWV086B-2", "WWV086B-3"]),
    ("Siegfried", ["WWV086C-1", "WWV086C-2", "WWV086C-3"]),
    ("Götterdämmerung", ["WWV086D-0", "WWV086D-1", "WWV086D-2", "WWV086D-3"]),
]
STEP_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PC_NAME = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"]
TIE_GAP = Fraction(1, 32)  # Sibelius rounds the durations of tuplets, so tied notes may miss by a little
SKIP_MAX = Fraction(1, 2)  # the longest note (in quarter notes) that find_core() skips in a sung passage: an ornament, not a syllable


LY_ALTER = {"isis": 2, "is": 1, "s": -1, "es": -1, "ses": -2, "eses": -2}  # the ending of a note name, in semitones
LY_TOKEN = re.compile(r"\s*(?:\\tuplet\s+(\d+)/(\d+)\s*(\{)|(\})|(~?)([a-g](?:isis|eses|ses|is|es|s)?|r)([,']*)(\d*)(\.*))")


def ly_tokens(src):
    """Return the notes and rests of absolute LilyPond `src`, each as a namespace with: rest, tie, name, octave (the
    , and ' marks), den, dots, dur (in quarter notes) and tuplet. As in LilyPond, a note without a duration takes the
    duration of the one before it. In `\\tuplet a/b { ... }` the notes last min(a,b)/max(a,b) of their value, so 2/3 and
    3/2 both make a triplet; `tuplet` is (start, stop or middle, notes in the tuplet, notes it replaces), else None.
    Text that is not a note, a rest or a tuplet is an error: a note must never be skipped without a word."""
    out, last, scale, first, pos, src = [], None, Fraction(1), 0, 0, src.strip()
    while pos < len(src):
        m = LY_TOKEN.match(src, pos)
        if not m:
            raise ValueError(f"The melody has text that is not a note, a rest or a tuplet: {src[pos:pos + 20]!r}")
        pos = m.end()
        a, b, opens, closes, tie, name, octave, den, dots = m.groups()
        if opens:
            scale, first = Fraction(min(int(a), int(b)), max(int(a), int(b))), len(out)
        elif closes:
            for k, t in enumerate(out[first:]):
                t.tuplet = ("start" if k == 0 else "stop" if first + k == len(out) - 1 else "middle", scale.denominator, scale.numerator)
            scale = Fraction(1)
        else:
            if den and int(den) not in (1, 2, 4, 8, 16, 32, 64):
                raise ValueError(f"{name}{octave}{den} has a duration that LilyPond does not know.")
            if den or last:
                last = (den, dots) if den else last
            else:
                raise ValueError("The first note of the melody needs a duration.")
            den, dots = last
            out.append(SimpleNamespace(rest=name == "r", tie=bool(tie), name=name, octave=octave, den=int(den), dots=dots, tuplet=None,
                                       dur=Fraction(4, int(den)) * (2 - Fraction(1, 2 ** len(dots))) * scale))
    return out


def parse_ly(src):
    """Return [(pitch class, duration in quarter notes, MIDI pitch, the rest after it in quarter notes)] for the notes of
    absolute LilyPond `src`. ~ merges a tie. A rest at the start of the melody is dropped."""
    notes = []
    for t in ly_tokens(src):
        if t.rest:
            if notes:
                notes[-1] = (*notes[-1][:3], notes[-1][3] + t.dur)
            continue
        midi = 12 * (3 + t.octave.count("'") - t.octave.count(",") + 1) + STEP_PC[t.name[0].upper()] + LY_ALTER.get(t.name[1:], 0)
        if t.tie:
            notes[-1] = (notes[-1][0], notes[-1][1] + t.dur, notes[-1][2], notes[-1][3])
        else:
            notes.append((midi % 12, t.dur, midi, Fraction(0)))
    return notes


def collapse(notes):
    """Merge a run of notes that repeat one pitch, with no rest between them, into one note. Each result is
    (pitch class, duration, MIDI pitch, first and last index of its notes, the rest after it)."""
    out = []
    for i, (pc, dur, midi, gap) in enumerate(notes):
        if out and out[-1][2] == midi and not out[-1][5]:
            out[-1] = (pc, out[-1][1] + dur, midi, out[-1][3], i, gap)
        else:
            out.append((pc, dur, midi, i, i, gap))
    return out


DEF = IDEAL = MOTIF = N = CORE = None  # set by use()


def load_definition(motif_id):
    return json.loads((DEFINITIONS / f"{motif_id}.json").read_text(encoding="utf-8"))


def full_name(d):
    """Return the name of a definition as the page shows it. A leitmotif with lettered forms, such as Valhalla (A) and
    Valhalla (B), has one definition for each form: they share `name` and differ in `variant`."""
    return f"{d['name']} ({d['variant']})" if "variant" in d else d["name"]


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


def placed_run(act, merged):
    """Return the passage that the "place" of the definition names, in the form that make_run() gives: every note of the act that
    starts in the measures `from` to `to` (the measure `to` is not in it). A leitmotif that is no melody, such as the held E-flat of
    the opening of Das Rheingold, has no search: its one passage is placed by hand."""
    place = DEF["place"]
    number = lambda n: next(i for i, m in enumerate(act.measures) if m["number"] == n)
    notes = sorted((g for g in merged if act.offsets[number(place["from"])] <= g.onset < act.offsets[number(place["to"])]), key=lambda g: g.onset)
    return SimpleNamespace(length=N, start=0, groups=[[g] for g in notes], run=notes, before=[], after=[], shown=notes, skipped=[])


def read_act(path):
    """Return (tied-note-merged notes of both staves, per-measure info, measure start times, rests)."""
    raw, rests, measures = [], [], []
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
                    elif e.find("rest") is not None:  # not part of any search, but a passage shows the rests between its notes
                        rests.append(SimpleNamespace(part=pi, voice=e.findtext("voice") or "1", mi=mi, pos=start, dur=dur,
                                                     el=e, div=div, fifths=fifths, ts=ts, clef=clef))
                top = max(top, pos)
            if pi == 0:
                measures.append(dict(number=int(m.get("number")), nominal=Fraction(ts[0] * 4, ts[1]), fifths=fifths, ts=ts, len=top, els=[m]))
            else:
                measures[mi]["len"] = max(measures[mi]["len"], top)
                measures[mi]["els"].append(m)  # the <measure> of each part, for full_excerpt()
    offsets, t = [], Fraction(0)
    for m in measures:
        offsets.append(t)
        t += m["len"]
    for p in raw + rests:
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

    return merged, measures, offsets, rests


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


def follows(by, prev, g):
    """Tell whether note `g` can come after note `prev` in a passage. It cannot if it has another pitch and both start
    in the same chord of their line: a chord that repeats (a tremolo) holds every note of the melody at each step, so
    it would match any melody that uses those notes. A melody in thirds or sixths changes its chord at each step, so
    it passes, and so does a pitch that repeats."""
    chord = lambda n: {h.midi for h in by.get((n.line, n.onset), ())}
    return prev is None or g.midi == prev.midi or chord(prev) != chord(g)


def make_run(by, ends, groups, start, skipped=()):
    """Return a passage: `groups` of notes that match MOTIF from MOTIF[start], with the groups of the line before and after.
    `skipped` is [(note, k)] for the notes of the line that the match skips (see find_core()): the note comes before MOTIF[k]. They are in
    `shown`, so that the notation keeps the line whole, but not in `run`, which the full score marks."""
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
    skipped = list(skipped)
    return SimpleNamespace(length=len(groups), start=start, groups=groups, run=notes, before=before, after=after, skipped=skipped,
                           shown=flat(before) + sorted(notes + [h for h, _ in skipped], key=lambda n: n.onset) + flat(after))


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
    min_len = min(min_len, N, CORE[1] - CORE[0])  # a melody, or a core, of fewer notes needs all of them

    def extend(line, t, j, prev=None):
        best = []
        for g in by.get((line, t), ()):
            if g.midi % 12 != MOTIF[j][0] or not follows(by, prev, g):
                continue
            for group in repeats(by, g):
                if total(group) > MOTIF[j][1]:
                    break
                if total(group) == MOTIF[j][1]:
                    c = [group] + (extend(line, t + total(group) + MOTIF[j][5], j + 1, group[-1]) if j + 1 < N else [])
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
        phrase_start = c[0][0].onset - sum(m[1] + m[5] for m in MOTIF[:j])  # where MOTIF would begin, if this run were its start
        if phrase_start not in seen:
            seen.add(phrase_start)
            kept.append(make_run(by, ends, c, j))
    return kept


def sung_spans(singing, measures, offsets):
    """Return the passages that the singing annotations mark, as (start, end) in quarter notes from the start of the act, in time order,
    with the ones that overlap joined. `singing` is [(measure_start, measure_end, person, text)]."""
    first = {}
    for i, m in enumerate(measures):
        first.setdefault(m["number"], i)
    end_of_act = offsets[-1] + measures[-1]["len"]

    def at(thousandths):
        n, f = divmod(thousandths, 1000)
        return offsets[first[n]] + Fraction(f, 1000) * measures[first[n]]["nominal"] if n in first else end_of_act

    spans = []
    for a, b in sorted((at(round(s * 1000)), at(round(e * 1000) + 1)) for s, e, _, _ in singing):  # an end such as 380.999 is just before 381
        if spans and a <= spans[-1][1]:
            spans[-1] = (spans[-1][0], max(spans[-1][1], b))
        else:
            spans.append((a, b))
    return spans


def find_core(merged, transposed=False, wrong=0, length=None, sung=()):
    """Return the passages in which the notes MOTIF[CORE] have the same pitch classes, with any rhythm.

    If `transposed` is true, the passages have the same intervals instead, so the key may differ.
    `wrong` notes may be anything. `length` keeps only the first `length` notes of the core.
    Notes that repeat one pitch in a row count as one note.
    `sung` is the passages of the act that a singer sings (see sung_spans()). The voice has no staff of its own in the score: it is part
    of a piano staff, and the piano may play other notes that the voice does not sing (a triplet, say) in the same line. So in a sung
    passage a match may skip one note of the line, if it is short (SKIP_MAX) and between two notes of the match. The match has those
    notes in `skipped` (see make_run()).
    """
    by, ends = index(merged)
    lo = CORE[0]
    hi = CORE[1] if length is None else lo + length
    starts = [a for a, _ in sung]

    def singing(t):
        k = bisect_right(starts, t) - 1
        return k >= 0 and t < sung[k][1]

    def follow(line, t, i, prev, errors, allowed, skips):
        """Yield (groups, skipped) for each way to match the notes from MOTIF[lo + i] that start at `t`."""
        here = by.get((line, t), ())
        for g in here:
            pc, before = MOTIF[lo + i][0], MOTIF[lo + i - 1][0]
            right = (g.midi % 12 == pc) if not transposed else (i == 0 or (g.midi - prev.midi) % 12 == (pc - before) % 12)
            if errors + (not right) > allowed or not follows(by, prev, g):
                continue
            # Try every number of repeats, because a held chord note of the same pitch can run on after the melody.
            for group in repeats(by, g):
                if lo + i + 1 == hi:
                    yield [group], []
                else:
                    for gap in sorted({0, MOTIF[lo + i][5]}):  # a rest of the melody may be missing in the score
                        for rest, skipped in follow(line, group[-1].onset + group[-1].dur + gap, i + 1, group[-1], errors + (not right), allowed, skips):
                            yield [group] + rest, skipped
        if skips and i > 0 and singing(t):
            for h in here:
                if h.dur <= SKIP_MAX:
                    for rest, skipped in follow(line, h.onset + h.dur, i, prev, errors, allowed, skips - 1):
                        yield rest, [(h, lo + i)] + skipped

    # Passages may overlap. Starts at the repeats of the first note give the same statement, and so does
    # the same statement in two staves, so each statement is kept once, at its earliest start.
    best = {}
    for line, t in by:
        found = []
        for skips in range(2 if sung else 1):  # a start that matches without a skipped note needs none
            for allowed in range(wrong + 1):  # a start that has an exact match needs no wrong note
                # Each wrong note multiplies the ways to match, so look at a limited number of them only.
                found = list(islice(follow(line, t, 0, None, 0, allowed, skips), MAX_CHAINS))
                if found:
                    break
            if found:
                break
        if found:
            c, skipped = min(found, key=lambda f: (shape_error(f[0], lo), -len(f[0][0])))
            span = (c[0][0].onset, c[-1][-1].onset + c[-1][-1].dur)
            if (line, span[1]) not in best or span[0] < best[(line, span[1])][0][0]:
                best[(line, span[1])] = (span, c, skipped)
    return [make_run(by, ends, c, lo, skipped) for _, c, skipped in sorted({span: (span, c, skipped) for span, c, skipped in best.values()}.values(), key=lambda h: h[0])]


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


def skip_text(run):
    """Return the text that tells which notes of a sung passage a core match skips."""
    parts = [f"{describe(h.midi % 12, h.dur)} between your notes {numbers(k - 1, 1)[1]} and {numbers(k, 1)[0]}" for h, k in run.skipped]
    return (f"The passage is sung, and the score has {' and '.join(parts)} in the same line. The voice has no staff of its own, so "
            f"{'this note is' if len(parts) == 1 else 'these notes are'} left out of the match.")


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


def write_attributes(m, p, last):
    """Append to measure `m` the attributes (divisions, key, time, clef) of the note `p` that differ from `last`, the ones before it,
    and return the ones of `p`."""
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
    return now


def move(tag, quarters, div):
    """Return a <backup> or <forward> of `quarters` quarter notes, in divisions of `div`."""
    e = ET.Element(tag)
    ET.SubElement(e, "duration").text = str(round(quarters * div))
    return e


def set_voice(n, voice):
    """Give the note or rest `n` the voice number `voice`."""
    tag = n.find("voice")
    if tag is None:
        tag = ET.Element("voice")
        n.insert(1 + max(i for i, c in enumerate(n) if c.tag in ("duration", "tie")), tag)
    tag.text = voice


def excerpt(chain, measures, rests=(), tempo=None):
    """Return a MusicXML score of the source notes of one match.

    The notes are copies of the notes in the score, so the clef, key, time signature, octave, rhythm,
    accidentals, stems, beams and ties are the ones of the score. Other notes are left out. The rests of the same
    staff and voice between the first and the last note are copied too, so that a melody with rests shows them. A rest
    that a chosen note sounds through (a chord with a shorter tone) is left out, because the notes follow each other.
    `tempo` is in quarter notes per minute. It sets the speed of the sound and shows nothing in the engraving.

    The notes of one line (a staff and voice) follow each other, and the measures that have none are left out. If `chain` has
    more than one line (see join_runs()), each staff of the score is a part, each voice of it a voice, and every measure from the
    first to the last is there, so that the lines keep their places in time. The first measure starts where the first note is.
    """
    pieces = sorted((p for g in chain for p in g.pieces), key=lambda p: p.onset)
    lines_of = {id(p): g.line for g in chain for p in g.pieces}  # a tie may go on in another voice number: the piece stays in the line of its note
    line = lambda p: lines_of.get(id(p), (p.part, p.voice))
    notes = []
    for p in pieces:
        n = copy.deepcopy(p.el)
        n.attrib.clear()
        for tag in ("chord", "instrument", "lyric"):
            for x in n.findall(tag):
                n.remove(x)
        notes.append(n)
    lines = sorted({line(p) for p in pieces})
    for l in lines:
        trim_spans([n for p, n in zip(pieces, notes) if line(p) == l])  # a beam, slur or tuplet never runs from one line to another

    items = list(zip(pieces, notes))
    for r in rests:
        mine = [p for p in pieces if line(p) == (r.part, r.voice)]
        if not mine:
            continue
        start, end = mine[0].onset, max(p.onset + p.dur for p in mine)
        gap = all(r.onset + r.dur <= p.onset + TIE_GAP or r.onset >= p.onset + p.dur - TIE_GAP for p in mine)  # a chord of the voice may sound through a rest
        if r.onset >= start - TIE_GAP and r.onset + r.dur <= end + TIE_GAP and gap:
            n = copy.deepcopy(r.el)
            n.attrib.clear()
            for tag in ("instrument", "notations"):  # a tuplet mark may lose its other end in the cut
                for x in n.findall(tag):
                    n.remove(x)
            items.append((r, n))
    items.sort(key=lambda item: item[0].onset)

    aligned = len(lines) > 1
    first, last_mi = min(p.mi for p, _ in items), max(p.mi for p, _ in items)
    shift = min(p.pos for p, _ in items if p.mi == first)  # the first measure starts at the first note, so that a pickup shows as one
    root = ET.Element("score-partwise", version="3.0")
    names = ET.SubElement(root, "part-list")
    parts = sorted({p.part for p, _ in items})
    if len(parts) > 1:
        brace = ET.SubElement(names, "part-group", type="start", number="1")
        ET.SubElement(brace, "group-symbol").text = "brace"
        ET.SubElement(brace, "group-barline").text = "yes"
    for k, part_index in enumerate(parts, start=1):
        ET.SubElement(ET.SubElement(names, "score-part", id=f"P{k}"), "part-name")
        part, state = ET.SubElement(root, "part", id=f"P{k}"), None
        mine = [(p, n) for p, n in items if p.part == part_index]
        numbered = len({line(p)[1] for p, _ in mine}) > 1  # the voices of a staff need a number of their own
        for mi in range(first, last_mi + 1) if aligned else sorted({p.mi for p, _ in mine}):
            m = ET.SubElement(part, "measure", number=str(measures[mi]["number"]))
            here = [(p, n) for p, n in mine if p.mi == mi]
            if state is None:  # before anything that has a duration; a staff that starts after the first measure has its clef there too
                state = write_attributes(m, mine[0][0], None)
            if mi == first and shift > 0:
                m.set("implicit", "yes")  # the match starts with a pickup
            if not here:  # a measure in which this staff has no note, but the key and the meter of the score may change in it
                key, time = measures[mi]["fifths"], measures[mi]["ts"]
                if (state["key"], state["time"]) != (key, time):
                    a = ET.SubElement(m, "attributes")
                    if state["key"] != key:
                        ET.SubElement(ET.SubElement(a, "key"), "fifths").text = str(key)
                    if state["time"] != time:
                        t = ET.SubElement(a, "time")
                        for tag, value in zip(("beats", "beat-type"), time):
                            ET.SubElement(t, tag).text = str(value)
                    state = dict(state, key=key, time=time)
                rest = ET.SubElement(m, "note")
                ET.SubElement(rest, "rest", measure="yes")
                ET.SubElement(rest, "duration").text = str(round(measures[mi]["nominal"] * state["divisions"]))
                continue
            origin = shift if mi == first else Fraction(0)  # the position in the measure that the first note of a voice is measured from
            voices = sorted({line(p)[1] for p, _ in here})
            for v in voices:
                at = origin  # where the voice is, in quarter notes from the start of the measure
                for p, n in (h for h in here if line(h[0])[1] == v):
                    if aligned and p.pos > at + TIE_GAP:  # a voice that starts late in the measure
                        m.append(move("forward", p.pos - at, p.div))
                        at = p.pos
                    state = write_attributes(m, p, state)
                    if numbered:
                        set_voice(n, v)
                    m.append(n)
                    at += Fraction(int(n.findtext("duration")), p.div)  # the written length: the export may give a chord note another length than its start tells
                if v != voices[-1]:
                    m.append(move("backup", at - origin, p.div))
        if part_index == parts[0] and tempo:
            direction = ET.Element("direction")  # Verovio prints an empty tempo mark as nothing
            ET.SubElement(ET.SubElement(direction, "direction-type"), "words")
            ET.SubElement(direction, "sound", tempo=str(tempo))
            part[0].insert(1, direction)  # after the attributes of the first measure
    if len(parts) > 1:
        ET.SubElement(names, "part-group", type="stop", number="1")
    for e in root.iter():  # drop the indentation that the copied notes carry
        e.tail = None
        if e.text and not e.text.strip():
            e.text = None
    return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(root, encoding="unicode")


STYLE_ATTRS = {"color", "default-x", "default-y", "relative-x", "relative-y", "width", "font-family", "font-size", "font-style",
               "font-weight", "justify", "valign", "halign"}  # how Sibelius drew the page; the page engraves the music again
DROPPED = {"print", "direction", "instrument", "lyric", "staff-details", "footnote", "level"}


def clean(e):
    """Remove from the copied element `e` what a full-score excerpt does not need: the page layout, the directions, and the style."""
    for c in list(e):
        if c.tag in DROPPED:
            e.remove(c)
        else:
            clean(c)
    for a in STYLE_ATTRS & set(e.attrib):
        del e.attrib[a]


def full_excerpt(run, measures, tempo=None):
    """Return a MusicXML score of the whole piano score (both staves) in the measures that the notes of `run.shown` span.

    The measures are copies of the score, so every note, rest, tie and beam is there. The notes that are part of the
    passage (`run.run`) carry an id that starts with "motif-", so that the page can draw them in color. The directions
    (dynamics, words and tempo marks) are left out, as in excerpt(). `tempo` is as in excerpt().
    """
    pieces = [p for g in run.shown + run.run for p in g.pieces]
    first, last = min(p.mi for p in pieces), max(p.mi for p in pieces)
    mine = {id(p.el) for g in run.run for p in g.pieces}
    root = ET.Element("score-partwise", version="3.0")
    names = ET.SubElement(root, "part-list")
    brace = ET.SubElement(names, "part-group", type="start", number="1")
    ET.SubElement(brace, "group-symbol").text = "brace"
    ET.SubElement(brace, "group-barline").text = "yes"
    count = 0
    for k in range(len(measures[0]["els"])):
        ET.SubElement(ET.SubElement(names, "score-part", id=f"P{k + 1}"), "part-name")
        part, state = ET.SubElement(root, "part", id=f"P{k + 1}"), {}
        for mi in range(first):  # the clef, key and time that are in effect where the excerpt starts
            for a in measures[mi]["els"][k].findall("attributes"):
                state.update((c.tag, c) for c in a)
        for mi in range(first, last + 1):
            src = measures[mi]["els"][k]
            m = copy.deepcopy(src)
            for s, d in zip(src.iter("note"), m.iter("note")):
                if id(s) in mine:
                    d.set("id", f"motif-{count}")
                    count += 1
            clean(m)
            if mi == first:
                attributes = ET.Element("attributes")
                attributes.extend(copy.deepcopy(state[t]) for t in ("divisions", "key", "time", "staves", "clef") if t in state)
                clean(attributes)
                m.insert(0, attributes)
            part.append(m)
    if tempo:
        direction = ET.Element("direction")
        ET.SubElement(ET.SubElement(direction, "direction-type"), "words")
        ET.SubElement(direction, "sound", tempo=str(tempo))
        root.find("part")[0].insert(1, direction)
    ET.SubElement(names, "part-group", type="stop", number="1")
    for e in root.iter():
        e.tail = None
        if e.text and not e.text.strip():
            e.text = None
    return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(root, encoding="unicode")


def locate(act, t):
    """Return the score position (a measure number with a fraction) of the time `t`, in quarter notes from the start of `act`."""
    mi = bisect_right(act.offsets, t) - 1
    return act.measures[mi]["number"] + round(float((t - act.offsets[mi]) / act.measures[mi]["nominal"]), 3)


def span(run, act):
    """Return the score positions where the notes that `run` shows start and end."""
    return locate(act, min(n.onset for n in run.shown)), locate(act, max(n.onset + n.dur for n in run.shown))


def join_overlapping(entries, gap):
    """Return `entries` ((level, run, act) for each passage) in lists: the passages of one act that overlap, or lie within
    `gap` measures of each other, are in one list, so a chain of such passages is one list. The passages may be in different
    staves and voices (see excerpt())."""
    joined = []
    for entry in sorted(entries, key=lambda e: (e[2].work, span(e[1], e[2])[0])):
        if joined and entry[2] is joined[-1][0][2] and span(entry[1], entry[2])[0] <= max(span(e[1], e[2])[1] for e in joined[-1]) + gap:
            joined[-1].append(entry)
        else:
            joined.append([entry])
    return joined


def join_runs(runs, by):
    """Return one passage, with the `run` and `shown` of make_run(), from `runs`, the closest first: the notes that any of them
    shows, in time order. The passages may be in different lines (a staff and voice). A voice of the score may hold two strands, and
    two passages may read them differently, so a note that would sound with one already taken in its line is left out of `shown`: the
    notes that a passage matched come first, in the order of `runs`, then the notes around them. Where two passages of a line leave a
    gap, the passage follows the line across it, as make_run() does for the notes around a passage. `run` has every note that any
    passage matched, also one that `shown` leaves out, because the full score marks them all."""
    mine = {id(n): n for r in runs for n in r.run}
    taken = []
    for n in [n for r in runs for n in r.run] + [n for r in runs for n in r.shown]:
        if all(t.line != n.line or n.onset >= t.onset + t.dur - TIE_GAP or n.onset + n.dur <= t.onset + TIE_GAP for t in taken):
            taken.append(n)
    shown = []
    for line in sorted({n.line for n in taken}):
        so_far = []
        for n in sorted((n for n in taken if n.line == line), key=lambda n: n.onset):
            while so_far and so_far[-1].onset + so_far[-1].dur < n.onset - TIE_GAP:
                ahead = [c for c in by.get((line, so_far[-1].onset + so_far[-1].dur), ()) if c.onset + c.dur <= n.onset + TIE_GAP]
                if not ahead:
                    break
                so_far.append(min(ahead, key=lambda c: abs(c.midi - so_far[-1].midi)))
            so_far.append(n)
        shown += so_far
    shown.sort(key=lambda n: n.onset)
    return SimpleNamespace(run=sorted(mine.values(), key=lambda n: n.onset), shown=shown)


def original_musicxml():
    """Return the MusicXML score of the melody, which the page engraves and plays like a passage of the score.

    The score has the time and the pickup that the definition gives, and its clef ("clef": "bass", else treble) and
    key signature ("key_signature": the number of sharps, or minus the number of flats, else none). It has one
    tie for each ~ of the melody. A note or a rest that crosses a barline becomes two (the notes tied). The notes
    shorter than a quarter note in one beat are beamed. A tuplet gets its bracket.
    """
    original = DEF["original"]
    beats, unit = map(int, original["time"].split("/"))
    tokens = ly_tokens(DEF["lilypond"])
    fine = 4 if any(t.den == 64 for t in tokens) else 2 if any(t.den == 32 for t in tokens) else 1
    s = fine * (3 if any(t.tuplet for t in tokens) else 1)  # units in a sixteenth note: 32nd and 64th notes and triplets need finer ones
    bar = 16 * s * beats // unit  # units in a bar
    group = (6 if unit == 8 and beats % 3 == 0 else 16 // unit) * s  # units in a beat; a beam stops at the end of a beat
    kinds = {v * s: k for v, k in [(24, ("whole", 1)), (16, ("whole", 0)), (14, ("half", 2)), (12, ("half", 1)), (8, ("half", 0)), (7, ("quarter", 2)),
                                   (6, ("quarter", 1)), (4, ("quarter", 0)), (3, ("eighth", 1)), (2, ("eighth", 0)), (1, ("16th", 0))]}
    if fine >= 2:
        kinds[s // 2] = ("32nd", 0)
    if fine == 4:
        kinds[s // 4] = ("64th", 0)
    units = lambda den, dots: int(Fraction(16 * s, int(den)) * (2 - Fraction(1, 2 ** len(dots))))  # the written value of a note
    pickup = units(*re.fullmatch(r"(\d+)(\.*)", original["partial"]).groups()) if original.get("partial") else 0
    notes, pos = [], (bar - pickup) % bar  # pos counts units from the start of the first bar
    for i, t in enumerate(tokens):
        pitch = None if t.rest else (t.name[0].upper(), LY_ALTER.get(t.name[1:], 0),
                                     3 + t.octave.count("'") - t.octave.count(",") + original["octaves_up"])
        tied_on = i + 1 < len(tokens) and tokens[i + 1].tie
        written, span = units(t.den, t.dots), int(t.dur * 4 * s)
        if t.tuplet:  # a note of a tuplet keeps its written value and is never split
            pieces, pos = [(written, pos)], pos + span
        else:
            remaining, pieces = span, []
            while remaining:
                room = min(remaining, bar - pos % bar)  # up to the next barline
                while room:
                    part = next(v for v in kinds if v <= room)  # the longest note value that fits
                    pieces.append((part, pos))
                    room, remaining, pos = room - part, remaining - part, pos + part
        for k, (part, at) in enumerate(pieces):
            notes.append(dict(pitch=pitch, units=part, span=span if t.tuplet else part, pos=at, measure=at // bar, tuplet=t.tuplet,
                              tie_stop=pitch is not None and (t.tie if k == 0 else True),
                              tie_start=pitch is not None and (True if k < len(pieces) - 1 else tied_on)))

    run = []
    def beam_run():
        for j, n in enumerate(run if len(run) > 1 else []):
            n["beam"] = "begin" if j == 0 else "end" if j == len(run) - 1 else "continue"
        run.clear()
    for n in notes:
        beamable = n["pitch"] is not None and n["units"] < 4 * s
        if run and not (beamable and n["pos"] // group == run[-1]["pos"] // group):
            beam_run()
        if beamable:
            run.append(n)
    beam_run()

    fifths = original.get("key_signature", 0)
    signature = {step: 1 if fifths > 0 else -1 for step in ("FCGDAEB"[:fifths] if fifths > 0 else "BEADGCF"[:-fifths])}
    measures, in_effect = defaultdict(str), {}  # in_effect: the accidental of a pitch in the bar, as the reader remembers it
    for n in notes:
        kind, dots = kinds[n["units"]]
        if n["pos"] % bar == 0 or n["pos"] == bar - pickup:
            in_effect = {}
        accidental, what = "", "<rest/>"
        if n["pitch"] is not None:
            step, alter, octave = n["pitch"]
            if not n["tie_stop"] and in_effect.get((step, octave), signature.get(step, 0)) != alter:  # a note tied from the last bar needs none
                accidental = f"<accidental>{ {-2: 'flat-flat', -1: 'flat', 0: 'natural', 1: 'sharp', 2: 'double-sharp'}[alter] }</accidental>"
                in_effect[(step, octave)] = alter
            what = f"<pitch><step>{step}</step>{f'<alter>{alter}</alter>' if alter else ''}<octave>{octave}</octave></pitch>"
        place, actual, normal = n["tuplet"] or (None, 0, 0)
        notations = ('<tied type="stop"/>' * n["tie_stop"] + '<tied type="start"/>' * n["tie_start"]
                     + {"start": '<tuplet type="start" bracket="yes"/>', "stop": '<tuplet type="stop"/>'}.get(place, ""))
        measures[n["measure"]] += (f"<note>{what}<duration>{n['span']}</duration>" + '<tie type="stop"/>' * n["tie_stop"] + '<tie type="start"/>' * n["tie_start"]
                                   + f"<voice>1</voice><type>{kind}</type>" + "<dot/>" * dots + accidental
                                   + (f"<time-modification><actual-notes>{actual}</actual-notes><normal-notes>{normal}</normal-notes></time-modification>" if place else "")
                                   + (f'<beam number="1">{n["beam"]}</beam>' if n.get("beam") else "")
                                   + (f"<notations>{notations}</notations>" if notations else "") + "</note>")
    clef = "<sign>F</sign><line>4</line>" if original.get("clef") == "bass" else "<sign>G</sign><line>2</line>"
    attributes = (f"<attributes><divisions>{4 * s}</divisions><key><fifths>{fifths}</fifths></key><time><beats>{beats}</beats><beat-type>{unit}</beat-type></time>"
                  f"<clef>{clef}</clef></attributes>")
    first = 0 if pickup else 1  # the number of the first measure: 0 for a pickup bar
    body = "".join(f'<measure number="{m + first}"{" implicit=" + chr(34) + "yes" + chr(34) if m == 0 and pickup else ""}>{attributes if m == 0 else ""}{xml}</measure>'
                   for m, xml in sorted(measures.items()))
    return ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.0"><part-list><score-part id="P1"><part-name/></score-part></part-list>'
            f'<part id="P1">{body}</part></score-partwise>')


def original_occurrence(at):
    """Return the occurrence that holds the original melody, at measure `at` of its section."""
    up, words = DEF["original"]["octaves_up"], {1: "one", 2: "two", 3: "three"}
    pickups = {"2": "half", "4": "quarter", "8": "eighth", "16": "sixteenth"}
    sig, partial = DEF["original"].get("key_signature", 0), DEF["original"].get("partial")
    pickup = f"one {'dotted ' if partial.endswith('.') else ''}{pickups.get(partial.rstrip('.'), partial)} note" if partial else ""
    key = f"{words.get(abs(sig), abs(sig))} {'sharp' if sig > 0 else 'flat'}{'' if abs(sig) == 1 else 's'} in the key signature" if sig else "no key signature"
    return dict(
        id="original", act=ORIGINAL_ACT, level=0, scene=None, label="The original",
        note=(f"The melody as you gave it, {words.get(abs(up), abs(up))} octave{'' if abs(up) == 1 else 's'} {'higher' if up > 0 else 'lower'}, " if up else "The melody as you gave it, ")
             + f"engraved from your notes. {f'It starts with a pickup of {pickup}' if partial else 'It has no pickup'}, "
             f"the bars are in {DEF['original']['time']}, and the score has a {DEF['original'].get('clef', 'treble')} clef and {key}. It is not a passage of the score.",
        libretto=None, notation=dict(musicxml=original_musicxml(), **original_svg()), **{"from": at, "to": at + 1})


def original_svg():
    """Return {"svg": ...}, the full transcription of the melody as the user engraved it (tools/engrave_originals.py), if
    leitmotifs/originals/<id>.svg exists. The page then shows it instead of the one-line engraving of original_musicxml()."""
    path = ROOT / "leitmotifs" / "originals" / f"{DEF['id']}.svg"
    return {"svg": path.read_text(encoding="utf-8")} if path.exists() else {}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def seconds_at(path):
    """Return a function from a score position (a measure number with a fraction) to its time in the recording, in
    seconds, by linear interpolation between the measure times of `path` (an ann_audio_measure file). It returns None
    outside the measures that the file lists. The last row is the end of the act, at a position such as 1732.999, so
    the whole number after it (where a passage at the end of the act stops) still counts."""
    rows = [(float(r["measure"]), float(r["start"])) for r in read_csv(path)]
    numbers = [m for m, _ in rows]

    def at(position):
        i = min(bisect_right(numbers, position) - 1, len(rows) - 2)
        if i < 0 or position - numbers[-1] > 0.002:
            return None
        (m0, t0), (m1, t1) = rows[i], rows[i + 1]
        return t0 + (t1 - t0) * (position - m0) / (m1 - m0)
    return at


def motif_block():
    """Return the "motif" part of a motif file: the id, the name, a description, and the source of the melody. The
    definition names its source by a key of leitmotifs/sources.json, so that one citation serves every leitmotif."""
    block = dict(id=DEF["id"], name=full_name(DEF),
                 description="Passages of the piano score that match one melody, in levels by how close they are to it. Level 1 is the closest. A run of repeated notes counts as one note."
                 f" Passages that overlap, or lie within {MERGE_GAP} measure{'' if MERGE_GAP == 1 else 's'} of each other, are joined into one; the level is that of the closest.")
    if "source" in DEF:
        block["source"] = json.loads((ROOT / "leitmotifs" / "sources.json").read_text(encoding="utf-8"))[DEF["source"]]
    return block


def write_index():
    """Write leitmotifs/motifs/index.json, the list that the page shows down its left side. If leitmotifs/order.json exists, the list is
    exactly its ids, in that order (the order of the book), and a leitmotif that is not in it stays on disk but is not listed. Without
    order.json, the list has every definition that has a motif file, in the order of the names."""
    folder = ROOT / "leitmotifs" / "motifs"
    order_ids = json.loads((ROOT / "leitmotifs" / "order.json").read_text(encoding="utf-8")) if (ROOT / "leitmotifs" / "order.json").exists() else None
    found = [load_definition(p.stem) for p in DEFINITIONS.glob("*.json") if (folder / p.name).exists() and (order_ids is None or p.stem in order_ids)]
    plain = lambda name: "".join(c for c in unicodedata.normalize("NFD", name) if not unicodedata.combining(c)).casefold()
    order_file = ROOT / "leitmotifs" / "order.json"
    rank = {m: i for i, m in enumerate(json.loads(order_file.read_text(encoding="utf-8")) if order_file.exists() else [])}
    listing = [dict(id=d["id"], name=full_name(d), **({"group": d["name"], "variant": d["variant"]} if "variant" in d else {}))
               for d in sorted(found, key=lambda d: (rank.get(d["id"], len(rank)), plain(d["name"]), d.get("variant", "")))]
    (folder / "index.json").write_text(json.dumps(dict(motifs=listing), ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("motif", help="the id of a definition in leitmotifs/definitions, for example siegfried")
    ap.add_argument("--data", type=pathlib.Path, default=ROOT / "data")
    ap.add_argument("--out", type=pathlib.Path, help="default: leitmotifs/motifs/<id>.json")
    ap.add_argument("--closest", type=int, default=2, help="partial matches of the whole phrase that make level 1, if none is complete")
    ap.add_argument("--refresh", action="store_true",
                    help="only refresh the texts of the existing output file (the translations and the level descriptions) and the original melody, without the search (a few seconds)")
    args = ap.parse_args()
    use(load_definition(args.motif))
    listed = args.out is None  # a file in another place is a trial run: leave the list of the page alone
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
        data["motif"] = motif_block()
        data["levels"] = levels()
        data["occurrences"] = [original_occurrence(o["from"]) if o["id"] == "original" else o for o in data["occurrences"]]
        args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"texts refreshed in {args.out}")
        for text in sorted(missing):
            print(f"no English in translations.json for: {text}")
        if listed:
            write_index()
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

            merged, measures, offsets, rests = read_act(score / f"Wagner_{work}.xml")
            singing = [(float(r["measure_start"]), float(r["measure_end"]), r["person"], r["text"])
                       for r in read_csv(f"{ann}/ann_score_singing/Wagner_{work}.csv")]
            act = SimpleNamespace(work=work, scenes=scenes, singing=singing, measures=measures, offsets=offsets, rests=rests, by=index(merged)[0],
                                  sung=sung_spans(singing, measures, offsets),
                                  seconds=seconds_at(f"{ann}/ann_audio_measure/Wagner_{work}_{PERFORMANCE}.csv"))
            if "place" in DEF:  # no search: the one passage is placed by hand
                if work == DEF["place"]["act"]:
                    runs.append((placed_run(act, merged), act))
                continue
            top = DEF.get("max_level", 9)  # a definition may drop the farther levels: for a very short melody they are all chance
            runs += [(run, act) for run in find_runs(merged)]
            if top >= 2:
                cores += [(run, act) for run in find_core(merged, sung=act.sung)]
            if top >= 3:
                wrongs += [(run, act) for run in find_core(merged, wrong=1)]
            if top >= 4:
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

    def build(groups):
        """Return the occurrences of `groups`, and their full scores by id. A group is a list of passages (level, run, act)
        that make one example: the closest of them names it."""
        occurrences, wholes = [], {}
        for members in groups:
            level, run, act = min(members, key=lambda m: m[0])
            whole = join_runs([m[1] for m in sorted(members, key=lambda m: m[0])], act.by) if len(members) > 1 else run  # what the excerpt shows
            a, b = span(whole, act)
            t0, t1 = act.seconds(a), act.seconds(b)
            quarters = max(n.onset + n.dur for n in whole.shown) - min(n.onset for n in whole.shown)
            tempo = round(60 * float(quarters) / (t1 - t0), 1) if t0 is not None and t1 is not None and t1 > t0 else None
            same_rhythm = all(total(g) == m[1] for g, m in zip(run.groups, MOTIF[run.start:])) and all(
                nxt[0].onset - (g[-1].onset + g[-1].dur) == m[5] for g, nxt, m in zip(run.groups, run.groups[1:], MOTIF[run.start:]))  # the rests too
            if "place" in DEF:
                label, note = DEF["place"]["label"], DEF["place"].get("note")
            elif level == 1:
                first, last = numbers(run.start, run.length)
                label = "Exact match" if run.length == N else f"Closest match: {last - first + 1} of {len(IDEAL)} notes"
                note = None if run.length == N else difference(run)
            elif level == 2:
                label = "Same pitches and rhythm" if same_rhythm else "Same pitches, different rhythm"
                note = None if same_rhythm else rhythm_difference(run)
                if run.skipped:
                    label = "Same pitches, sung, one note skipped"
                    note = f"{rhythm_difference(run)} {skip_text(run)}"
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
            if len(members) > 1:
                levels_of = ", ".join(str(m[0]) for m in sorted(members, key=lambda m: m[0]))
                label += f", joined with {len(members) - 1} more"
                note = " ".join(filter(None, [note, f"This joins {len(members)} passages (levels {levels_of}) that overlap, or lie within {MERGE_GAP} measure{'' if MERGE_GAP == 1 else 's'} of each other."]))
            unique = f"{act.work[6:]}-{a:.3f}"
            while unique in {o["id"] for o in occurrences}:  # overlapping passages may begin at the same note
                unique += f"-L{level}"
            occurrences.append(dict(
                id=unique, act=act.work, level=level,
                scene=next((sc for s, e, sc in act.scenes if s <= a <= e + 0.001), None), label=label, note=note,
                libretto=[dict(kind="sung", person=p, text=x, **({"translation": translations[x]} if x in translations else {}))
                          for s, e, p, x in act.singing if s < b and e >= a],
                notation=dict(musicxml=excerpt(whole.shown, act.measures, act.rests, tempo)), **{"from": a, "to": b}))
            wholes[unique] = dict(musicxml=full_excerpt(whole, act.measures, tempo))
            untranslated.update(l["text"] for l in occurrences[-1]["libretto"] if "translation" not in l)
            print(f"level {level}  {act.work:10s} measure {a:9.3f}  {label}")
        # The original melody comes first. Its short section sits to the left of the start of Das Rheingold.
        occurrences.append(original_occurrence(width / 2))
        order = {s["act"]: i for i, s in enumerate(sections)}
        occurrences.sort(key=lambda o: (order[o["act"]], o["from"]))
        return occurrences, wholes

    width = round(sum(s["to"] - s["from"] for s in sections) * 0.04)
    sections.insert(0, dict(id="original", opera="", act=ORIGINAL_ACT, label="Original", short="Orig", original=True, **{"from": 0, "to": width}))
    entries = [(level, run, act) for level, found in sorted(found_at.items()) for run, act in found]
    groups = join_overlapping(entries, MERGE_GAP)
    occurrences, wholes = build(groups)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(dict(format=1, motif=motif_block(), levels=levels(), sections=sections, occurrences=occurrences), f, ensure_ascii=False, indent=1)
    with open(args.out.with_suffix(".full.json"), "w", encoding="utf-8") as f:  # the page loads it when the viewer asks for the full score
        json.dump(dict(format=1, occurrences=wholes), f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(occurrences)} occurrences written to {args.out} ({len(entries)} passages joined into {len(groups)} examples)")
    if listed:
        write_index()
    for text in sorted(untranslated):
        print(f"no English in {translations_path.name} for: {text}")


if __name__ == "__main__":
    main()
