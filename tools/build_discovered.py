"""Write the data that leitmotifs/index.html reads (format: leitmotifs/DATA-SPEC.md) for the leitmotifs that the
discovery run found (discovery/results/leitmotifs/LM*.json). The run only reads discovery/.

The page loads its data from motifs/ next to it. The data goes to leitmotifs-discovered/motifs/, and
leitmotifs-discovered/index.html is a link to leitmotifs/index.html, so the page and the 33 hand-defined leitmotifs stay as they are.

Discovery gives, for each occurrence, a stream of the piano score (T1/T2: the top notes of the right/left hand, B1/B2: the
bottom notes, L<part><staff><voice>: one voice) and a score position. It numbers measures by their row in the MusicXML file,
which is the number of the dataset except in WWV086B-2 and WWV086B-3 (the pickup is row 1 there, and measure 0 in the dataset).
This script cuts the same stream out of the score again (the skyline rule of discovery/tools/s02_streams.py), checks the
pitches against the ones that discovery lists, and copies the notes with excerpt() and full_excerpt() of tools/find_motif.py.
The sung text and the scene come from the dataset annotations at the corrected position, not from the text in the results.

The English of the sung lines is in leitmotifs/translations.json, as for the other leitmotifs. After a change to that file,
--refresh applies it to the existing output in a few seconds and lists each sung line that still has no English.

usage: python3 -I tools/build_discovered.py [--data DIR] [--out DIR] [--only LM001 LM002 ...] [--refresh]
"""
import argparse, importlib.util, json, math, os, pathlib, re, sys
from bisect import bisect_left, bisect_right
from collections import Counter
from fractions import Fraction
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT / "discovery" / "results" / "leitmotifs"
TOLERANCE = Fraction(1, 32)  # quarter notes: how far a note may be from the position that discovery gives
STRENGTH = {"strong": 0, "medium": 1, "weak": 2}  # the order of discovery/results/INDEX.md
SHOWN = {"T1": "the top notes of the right hand", "T2": "the top notes of the left hand",
         "B1": "the bottom notes of the right hand", "B2": "the bottom notes of the left hand"}
LEVELS = [
    dict(level=1, name="Exact", description="Every interval and every long or short note agrees with the pattern that discovery found."),
    dict(level=2, name="Approximate", description="A few intervals or rhythm classes differ from the pattern. Discovery accepts up to 15 % of the intervals and 25 % of the rhythm classes."),
]
PITCH = re.compile(r"([A-G])(#|x|bb|b|[+-]\d+)?(-?\d+)")
BASE = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)


def load(name):
    """Import tools/<name>.py. A script that runs with -I cannot import its neighbors."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def midi(name):
    """The MIDI pitch of a note name of discovery (C4, Db4, F#2), or None."""
    m = PITCH.fullmatch(name)
    if not m:
        return None
    step, acc, octave = m.groups()
    alter = int(acc) if acc and acc[0] in "+-" else {None: 0, "#": 1, "x": 2, "b": -1, "bb": -2}[acc]
    return 12 * (int(octave) + 1) + BASE[step] + alter


def skyline(groups, top):
    """Return the notes of `groups` (sorted by onset, then pitch) that the skyline of discovery keeps: the top (or bottom) note
    of each onset, except that a new note which is lower (higher) than a note that still sounds does not replace it."""
    sign = 1 if top else -1
    keep, held, end, i = [], None, None, 0
    while i < len(groups):
        j = i
        while j < len(groups) and groups[j].onset == groups[i].onset:
            j += 1
        best = max(groups[i:j], key=lambda g: sign * g.midi)
        if held is None or best.onset >= end or sign * best.midi >= sign * held:
            keep.append(best)
            held, end = best.midi, best.onset + best.dur
        i = j
    return keep


def stream(merged, name):
    """Return the notes of the stream `name` of one act, the repeated pitches included, in time order."""
    if name[0] in "TB":
        mine = [g for g in merged if g.line[0] == int(name[1]) - 1]
    else:
        line = int(name[1:])
        mine = [g for g in merged if g.line == (line // 100 - 1, str(line % 10)) and int(g.pieces[0].el.findtext("staff") or 1) == line // 10 % 10]
    return skyline(sorted(mine, key=lambda g: (g.onset, g.midi)), name[0] != "B")


def pitches(chain):
    """The pitches of `chain` with each run of one repeated pitch counted once, as discovery counts them."""
    out = []
    for g in chain:
        if not out or out[-1] != g.midi:
            out.append(g.midi)
    return out


def at(act, position):
    """Return the time in quarter notes from the start of `act` of a position of discovery: the row of the measure in the file,
    then the part of the measure."""
    row = int(position)
    return act.offsets[row - 1] + Fraction(position - row).limit_denominator(4096) * act.measures[row - 1]["nominal"]


def found_in(seen, listed):
    """Return where the pitches `listed` start in `seen`, or None. Discovery lists the notes of the longest statement of an
    occurrence, which can begin after the occurrence does and end after it (the list stops at 48 notes), so only as many
    pitches as `seen` has left are compared, and at least 4 of them unless `listed` is shorter."""
    for k in range(len(seen)):
        m = min(len(listed), len(seen) - k)
        if m < min(len(listed), 4):
            break
        if seen[k:k + m] == listed[:m]:
            return k
    return None


def follow(kept, i, listed):
    """Return the notes of `kept` from index `i` for as long as their pitches (a run of one pitch counts once) are the ones of
    `listed`, and how many pitches that is."""
    chain, count = [], 0
    for g in kept[i:]:
        if not chain or chain[-1].midi != g.midi:
            if count == len(listed) or listed[count] != g.midi:
                break
            count += 1
        chain.append(g)
    return chain, count


def cut(act, names, first, last, listed):
    """Return (stream name, chain, where the listed pitches start in the chain or None, whether the chain goes past `last`)
    for the stream of `names` that agrees best with the pitches that discovery lists. The chain runs from the note at the
    position `first` to the one at `last`. Where no stream agrees there, the chain follows a stream from `first` for as long
    as it plays the listed pitches: a few positions of discovery end before the notes that it lists."""
    t0, t1 = at(act, first), at(act, last)
    best, kept_of = None, {}
    for name in names:
        if name not in act.streams:
            act.streams[name] = stream(act.merged, name)
        kept = kept_of[name] = act.streams[name]
        onsets = [g.onset for g in kept]
        i, j = bisect_left(onsets, t0 - TOLERANCE), bisect_right(onsets, t1 + TOLERANCE)
        while 0 < j < len(kept) and kept[j].midi == kept[j - 1].midi:  # a repeated note at the end belongs to the last note
            j += 1
        chain = kept[i:j]
        seen = pitches(chain)
        where = found_in(seen, listed)
        score = (where is not None, -(where or 0), sum(a == b for a, b in zip(seen, listed)))
        if chain and (best is None or score > best[3]):
            best = (name, chain, where, score)
        if where is not None:
            return best[:3] + (False,)
    longest = None
    for name, kept in kept_of.items():
        chain, count = follow(kept, bisect_left([g.onset for g in kept], t0 - TOLERANCE), listed)
        if count >= min(len(listed), 4) and (longest is None or count > longest[2]):
            longest = (name, chain, count)
    if longest:
        return longest[0], longest[1], 0, True
    return best[:3] + (False,) if best else None


def sections_of(fm, ann):
    """The ribbon of the page: one section for each act, one for each scene of Das Rheingold (as in tools/find_motif.py)."""
    sections = []
    for opera, works in fm.OPERAS:
        for work in works:
            scenes = [(float(r["measure_start"]), float(r["measure_end"]), int(r["scene"])) for r in fm.read_csv(f"{ann}/ann_score_scenes/Wagner_{work}.csv")]
            end = math.floor(scenes[-1][1]) + 1
            if work == "WWV086A":
                for i, (start, _, sc) in enumerate(scenes):
                    sections.append(dict(id=f"A-{sc}", opera=opera, act=work, label=f"Scene {sc}", short=f"Sc {sc}",
                                         **{"from": start, "to": scenes[i + 1][0] if i + 1 < len(scenes) else end}))
            else:
                sections.append(dict(id=work[6:], opera=opera, act=work, label="Prologue" if work == "WWV086D-0" else f"Act {work[-1]}",
                                     **({"short": "Pro"} if work == "WWV086D-0" else {}), **{"from": scenes[0][0], "to": end}))
    return sections


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", type=pathlib.Path, default=ROOT / "data")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "leitmotifs-discovered")
    ap.add_argument("--only", nargs="+", metavar="LMnnn", help="only these leitmotifs (a trial run)")
    ap.add_argument("--refresh", action="store_true",
                    help="only refresh the English of the existing output files from leitmotifs/translations.json, without the search (a few seconds)")
    args = ap.parse_args()
    fm = load("find_motif")
    ann, score = args.data / "02_Annotations", args.data / "01_RawData" / "score_musicxml"
    translations = json.loads((ROOT / "leitmotifs" / "translations.json").read_text(encoding="utf-8"))

    if args.refresh:
        missing = set()
        for path in sorted((args.out / "motifs").glob("LM*.json")):
            if path.name.endswith(".full.json"):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for o in data["occurrences"]:
                for line in o["libretto"]:
                    line.pop("translation", None)
                    if line["text"] in translations:
                        line["translation"] = translations[line["text"]]
                    else:
                        missing.add(line["text"])
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"English refreshed in {args.out / 'motifs'}")
        for text in sorted(missing):
            print(f"no English in translations.json for: {text}")
        return

    found =[json.loads(p.read_text(encoding="utf-8")) for p in sorted(RESULTS.glob("LM*.json"))]
    found = [d for d in found if not args.only or d["id"] in args.only]
    found.sort(key=lambda d: (STRENGTH[d["strength"]], d["id"]))
    sections = sections_of(fm, ann)
    first_of = {}
    for s in sections:
        first_of.setdefault(s["act"], s["from"])
    order = {s["act"]: i for i, s in enumerate(sections)}

    made = {d["id"]: [] for d in found}  # the occurrences of each leitmotif
    wholes = {d["id"]: {} for d in found}
    stats, missing, problems = Counter(), set(), []
    for _, works in fm.OPERAS:
        for work in works:
            todo = [(d, o) for d in found for o in d["occurrences"] if o["act"] == work]
            if not todo:
                continue
            merged, measures, offsets, rests = fm.read_act(score / f"Wagner_{work}.xml")
            scenes = [(float(r["measure_start"]), float(r["measure_end"]), int(r["scene"])) for r in fm.read_csv(f"{ann}/ann_score_scenes/Wagner_{work}.csv")]
            singing = [(float(r["measure_start"]), float(r["measure_end"]), r["person"], r["text"]) for r in fm.read_csv(f"{ann}/ann_score_singing/Wagner_{work}.csv")]
            act = SimpleNamespace(work=work, merged=merged, measures=measures, offsets=offsets, rests=rests, streams={},
                                  seconds=fm.seconds_at(f"{ann}/ann_audio_measure/Wagner_{work}_{fm.PERFORMANCE}.csv"))
            for d, o in todo:
                listed = [midi(n) for n in o["notes"]]
                if not listed or None in listed:
                    stats["no list of notes"] += 1
                    problems.append(f"{d['id']} {work} {o['pos0']:.3f}: discovery lists no usable notes")
                    continue
                best = cut(act, o["streams"], o["pos0"], o["pos1"], listed)
                if best is None:
                    stats["no notes found"] += 1
                    problems.append(f"{d['id']} {work} {o['pos0']:.3f}: no note of {o['streams']} at that position")
                    continue
                name, chain, where, extended = best
                stats["window extended to the listed notes" if extended else "pitches agree" if where is not None else "pitches differ"] += 1
                if where is None:
                    problems.append(f"{d['id']} {work} {o['pos0']:.3f}: {name} differs from the listed pitches")
                run = SimpleNamespace(run=chain, shown=chain)
                a, b = fm.span(run, act)
                a = max(a, first_of[work])  # a pickup is before the first section
                t0, t1 = act.seconds(a), act.seconds(b)
                quarters = max(g.onset + g.dur for g in chain) - min(g.onset for g in chain)
                tempo = round(60 * float(quarters) / (t1 - t0), 1) if t0 is not None and t1 is not None and t1 > t0 else None
                exact = o["match"] == "exact"
                unique = f"{work[6:]}-{a:.3f}"
                while unique in {x["id"] for x in made[d["id"]]}:
                    unique += f"-{len(made[d['id']])}"
                lines = [dict(kind="sung", person=p, text=x, **({"translation": translations[x]} if x in translations else {}))
                         for s, e, p, x in singing if s < b and e >= a]
                missing.update(l["text"] for l in lines if "translation" not in l)
                shown = SHOWN.get(name, f"one voice of the {'right' if name[1] == '1' else 'left'} hand ({name})")
                made[d["id"]].append(dict(
                    id=unique, act=work, level=1 if exact else 2,
                    scene=next((sc for s, e, sc in scenes if s <= a <= e + 0.001), None),
                    label="Exact match" if exact else "Approximate match, " + o["match"].split("(")[1].rstrip(")"),
                    note=f"The notation shows {shown}. Discovery calls this {d['id']} ({d['strength']}). The reviewers' hints, which are guesses and not names: {d['reviewer_themes']}.",
                    libretto=lines, notation=dict(musicxml=fm.excerpt(chain, measures, rests, tempo)), **{"from": a, "to": b}))
                wholes[d["id"]][unique] = dict(musicxml=fm.full_excerpt(run, measures, tempo))
            print(f"{work}: {len(todo)} occurrences", flush=True)

    folder = args.out / "motifs"
    folder.mkdir(parents=True, exist_ok=True)
    for d in found:
        occurrences = sorted(made[d["id"]], key=lambda o: (order[o["act"]], o["from"]))
        levels = [l for l in LEVELS if any(o["level"] == l["level"] for o in occurrences)]
        motif = dict(id=d["id"], name=d["id"], description=f"{d['n_occurrences']} occurrences in {d['n_scenes']} scenes. Reviewers' hints, which are guesses and not names: {d['reviewer_themes']}.")
        with open(folder / f"{d['id']}.json", "w", encoding="utf-8") as f:
            json.dump(dict(format=1, motif=motif, levels=levels, sections=sections, occurrences=occurrences), f, ensure_ascii=False, separators=(",", ":"))
        with open(folder / f"{d['id']}.full.json", "w", encoding="utf-8") as f:
            json.dump(dict(format=1, occurrences=wholes[d["id"]]), f, ensure_ascii=False, separators=(",", ":"))
    (folder / "index.json").write_text(json.dumps(dict(motifs=[dict(id=d["id"], name=d["id"]) for d in found]), ensure_ascii=False, indent=1), encoding="utf-8")

    page = args.out / "index.html"
    if not page.is_symlink():
        os.symlink("../leitmotifs/index.html", page)

    link = load("link_motifs")  # the leitmotifs near each example
    link.MOTIFS = folder
    sys.argv = ["link_motifs.py", "--out", str(folder / "also.json")]
    link.main()

    print(f"{sum(len(v) for v in made.values())} occurrences of {len(found)} leitmotifs written to {folder}")
    for key, n in sorted(stats.items()):
        print(f"  {n:5d}  {key}")
    for line in problems[:40]:
        print("  problem:", line)
    print(f"{len(missing)} sung lines have no English in leitmotifs/translations.json")


if __name__ == "__main__":
    main()
