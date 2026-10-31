"""Count what each candidate for a next level would find, next to a noise baseline.

For each candidate the script counts the passages of the piano score that match (any rhythm unless the name
says otherwise, one staff and voice, repeated notes counted as one note), and how many of them are new, which
means that they do not lie inside an occurrence that is already in the motif file. Passages may overlap in
time. Two count as one only if they are the same statement: they end on the same note of the same staff and
voice, or they begin and end at the same moments.

The baseline is the same count for the same notes played backwards. A backwards melody has the same intervals and
does not occur on purpose, so its count is the number of passages that match by chance. If a candidate finds
hardly more passages than its backwards version, most of what it finds is chance.

Run tools/find_motif.py first: the script reads the occurrences that it wrote.

usage: python3 -I tools/analyze_levels.py MOTIF_ID [--data DIR] [--motif FILE]
"""
import argparse, importlib.util, json, pathlib, time
from bisect import bisect_right
from fractions import Fraction

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("find_motif", HERE / "find_motif.py")
fm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fm)


def load(data, motif):
    existing = {}
    for o in json.loads(motif.read_text(encoding="utf-8"))["occurrences"]:
        if o["act"] != fm.ORIGINAL_ACT:
            existing.setdefault(o["act"], []).append((o["from"], o["to"]))
    acts = {}
    for work in [w for _, ws in fm.OPERAS for w in ws]:
        merged, measures, offsets = fm.read_act(data / "01_RawData" / "score_musicxml" / f"Wagner_{work}.xml")
        acts[work] = (fm.index(merged)[0], measures, offsets)
    return acts, existing


def passages(acts, first_chain):
    """Return the passages [(act, start measure, end measure)] that `first_chain(by, line, t)` finds.
    `first_chain` returns the end time of the first chain that starts with a note at time t, or None."""
    found = []
    for work, (by, measures, offsets) in acts.items():
        def locate(t):
            mi = bisect_right(offsets, t) - 1
            return measures[mi]["number"] + float((t - offsets[mi]) / measures[mi]["nominal"])

        earliest = {}  # the same statement is found from each of its repeated first notes; keep the earliest start
        for line, t in list(by):
            end = first_chain(by, line, t)
            if end is not None and ((line, end) not in earliest or t < earliest[(line, end)]):
                earliest[(line, end)] = t
        spans = sorted({(start, end) for (line, end), start in earliest.items()})  # the same statement in two staves
        found += [(work, locate(start), locate(end)) for start, end in spans]
    return found


def pitch_search(seq, mode, tolerance):
    """Match the pitches of `seq`. mode: 'pc' same pitch classes, 'int' same intervals (any key),
    'mode' every interval within one semitone, 'third' within one semitone only where yours is a third or a sixth.
    `tolerance` notes may be wrong."""
    n = len(seq)

    def check(g, prev, i):
        if i == 0:
            return mode != "pc" or g.midi % 12 == seq[0]
        if mode == "pc":
            return g.midi % 12 == seq[i]
        target = (seq[i] - seq[i - 1]) % 12
        d = ((g.midi - prev.midi) - target) % 12
        loose = mode == "mode" or (mode == "third" and target in (3, 4, 8, 9))
        return d in (0, 1, 11) if loose else d == 0

    def first_chain(by, line, t):
        def follow(t, i, prev, errors):
            for g in by.get((line, t), ()):
                errors_now = errors + (0 if check(g, prev, i) else 1)
                if errors_now > tolerance:
                    continue
                group = list(fm.repeats(by, g))[-1]
                end = group[-1].onset + group[-1].dur
                if i + 1 == n:
                    yield end
                else:
                    yield from follow(end, i + 1, g, errors_now)
        return next(follow(t, 0, None, 0), None)

    return first_chain


def rhythm_search(durs, scaled):
    """Match the rhythm of `durs` with any pitches. If `scaled`, the whole rhythm may be longer or shorter."""
    n = len(durs)

    def first_chain(by, line, t):
        def follow(t, i, factor):
            for g in by.get((line, t), ()):
                for group in fm.repeats(by, g):
                    length = fm.total(group)
                    f = factor if factor is not None else (length / durs[0] if scaled else Fraction(1))
                    if length > durs[i] * f:
                        break
                    if length == durs[i] * f:
                        end = group[-1].onset + group[-1].dur
                        if i + 1 == n:
                            yield end
                        else:
                            yield from follow(end, i + 1, f)
        return next(follow(t, 0, None), None)

    return first_chain


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("motif", help="the id of a definition in leitmotifs/definitions, for example siegfried")
    ap.add_argument("--data", type=pathlib.Path, default=fm.ROOT / "data")
    ap.add_argument("--motif-file", dest="motif_file", type=pathlib.Path, help="default: leitmotifs/motifs/<id>.json")
    args = ap.parse_args()
    fm.use(fm.load_definition(args.motif))
    pcs, durs = [m[0] for m in fm.MOTIF], [m[1] for m in fm.MOTIF]  # the melody with repeated notes collapsed
    lo, hi = fm.CORE
    core = pcs[lo:hi]

    started = time.time()
    acts, existing = load(args.data, args.motif_file or fm.ROOT / "leitmotifs" / "motifs" / f"{fm.DEF['id']}.json")
    print(f"read the 11 acts in {time.time() - started:.0f} s; {sum(map(len, existing.values()))} occurrences are already listed")

    def is_new(f):
        return not any(f[0] == work and a - 0.001 <= f[1] and f[2] <= b + 0.001 for work, spans in existing.items() for a, b in spans)

    def report(name, make, forward, backward):
        real, noise = passages(acts, make(forward)), passages(acts, make(backward))
        print(f"  {name:48s} real {len(real):4d} (new {sum(map(is_new, real)):4d})   backwards {len(noise):4d}   ratio {len(real) / max(1, len(noise)):5.1f}")

    print(f"\nA. Fewer notes, same pitches in the original key (the {len(core)} core notes are notes {fm.DEF['core_notes'][0]}-{fm.DEF['core_notes'][1]})")
    for a, b, label in [(lo, hi, "the core notes (the current level 2)"), (lo, lo + 8, "the first 8 of them"), (lo, lo + 6, "the first 6"),
                        (lo, lo + 5, "the first 5"), (hi - 4, len(pcs), "the last notes of the melody")]:
        report(label, lambda s: pitch_search(s, "pc", 0), pcs[a:b], pcs[a:b][::-1])
    print("\nB. Fewer notes, same intervals in any key")
    for a, b, label in [(lo, hi, "the core notes (the current level 3)"), (lo, lo + 8, "the first 8 of them"), (lo, lo + 6, "the first 6"),
                        (lo, lo + 5, "the first 5"), (hi - 4, len(pcs), "the last notes of the melody")]:
        report(label, lambda s: pitch_search(s, "int", 0), pcs[a:b], pcs[a:b][::-1])
    print("\nC. One note may be wrong, in the core notes")
    report("same pitches, one note different", lambda s: pitch_search(s, "pc", 1), core, core[::-1])
    report("same intervals in any key, one different", lambda s: pitch_search(s, "int", 1), core, core[::-1])
    print("\nD. Major and minor variants: an interval may be one semitone off")
    report("core notes, every interval", lambda s: pitch_search(s, "mode", 0), core, core[::-1])
    report("core notes, only thirds and sixths", lambda s: pitch_search(s, "third", 0), core, core[::-1])
    report("the first 8 core notes, only thirds and sixths", lambda s: pitch_search(s, "third", 0), pcs[lo:lo + 8], pcs[lo:lo + 8][::-1])
    print("\nE. The rhythm of the core notes, with any pitches")
    report("same rhythm", lambda s: rhythm_search(s, False), durs[lo:hi], durs[lo:hi][::-1])
    report("same rhythm, longer or shorter by any factor", lambda s: rhythm_search(s, True), durs[lo:hi], durs[lo:hi][::-1])
    print(f"\ndone in {time.time() - started:.0f} s")


if __name__ == "__main__":
    main()
