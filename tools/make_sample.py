"""Write leitmotifs/motifs/sample.json, a test file for the page: the real sections of the Ring and made-up passages.

The sections are built from the dataset in the same way as in tools/find_motif.py. Every passage, text and note is
made up, and the random numbers are seeded, so the file is the same each time. Use it with index.html?motif=sample.

usage: python3 -I tools/make_sample.py [--data DIR] [--out FILE]
"""
import argparse, csv, json, math, pathlib, random

ROOT = pathlib.Path(__file__).resolve().parent.parent
OPERAS = [
    ("Das Rheingold", ["WWV086A"]),
    ("Die Walküre", ["WWV086B-1", "WWV086B-2", "WWV086B-3"]),
    ("Siegfried", ["WWV086C-1", "WWV086C-2", "WWV086C-3"]),
    ("Götterdämmerung", ["WWV086D-0", "WWV086D-1", "WWV086D-2", "WWV086D-3"]),
]
COUNTS = [2, 1, 0, 1, 2, 2, 2, 5, 4, 5, 2, 4, 2, 4]  # passages in each of the 14 sections
SINGERS = ["[placeholder singer one]", "[placeholder singer two]"]
LINES = ["[a short placeholder line]",
         "[placeholder sung text, first line,\nsecond line of the same phrase,\nand a third line to show wrapping]"]
DIRECTIONS = ["[placeholder stage direction]",
              "[a longer placeholder stage direction that runs over several lines, so the italic block can be judged at its natural width on a normal screen]"]
STEPS = "CDEFGAB"


def read_scenes(ann, work):
    with open(f"{ann}/ann_score_scenes/Wagner_{work}.csv", newline="") as f:
        return [(float(r["measure_start"]), float(r["measure_end"]), int(r["scene"])) for r in csv.DictReader(f, delimiter=";")]


def note(deg, dur, kind, alter=0):
    a = f"<alter>{alter}</alter>" if alter else ""
    return (f"<note><pitch><step>{STEPS[deg % 7]}</step>{a}<octave>{4 + deg // 7}</octave></pitch>"
            f"<duration>{dur}</duration><type>{kind}</type></note>")


def musicxml(rng, measures):
    base = rng.randint(0, 6)
    degs = [base + d for d in rng.choice([[0, 2, 4, 2], [0, 4, 2, 4], [0, 2, 3, 5]])]
    bad = rng.randrange(4) if rng.random() < 0.3 else None
    body = "".join(note(d, 2, "quarter", rng.choice([-1, 1]) if i == bad else 0) for i, d in enumerate(degs))
    if measures == 2:
        body += '</measure><measure number="2">' + note(degs[-1], 8, "whole")
    return ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.0"><part-list>'
            '<score-part id="P1"><part-name/></score-part></part-list><part id="P1"><measure number="1">'
            '<attributes><divisions>2</divisions><key><fifths>0</fifths></key>'
            '<time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef>'
            f'</attributes>{body}</measure></part></score-partwise>')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", type=pathlib.Path, default=ROOT / "data")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "leitmotifs" / "motifs" / "sample.json")
    args = ap.parse_args()
    ann = args.data / "02_Annotations"

    sections = []
    for opera, works in OPERAS:
        for work in works:
            rows = read_scenes(ann, work)
            end = math.floor(rows[-1][1]) + 1
            if work == "WWV086A":  # Rheingold is split into its four scenes
                for i, (start, _, sc) in enumerate(rows):
                    to = rows[i + 1][0] if i + 1 < len(rows) else end
                    sections.append(dict(id=f"A-{sc}", opera=opera, act=work, label=f"Scene {sc}", short=f"Sc {sc}", **{"from": start, "to": to}))
            else:
                tail = work.split("-")[-1] if "-" in work else ""
                sections.append(dict(id=work[6:], opera=opera, act=work, label="Prologue" if tail == "0" else f"Act {tail}",
                                     **({"short": "Pro"} if tail == "0" else {}), **{"from": rows[0][0], "to": end}))

    rng = random.Random(7)
    occurrences = []
    for s, n in zip(sections, COUNTS):
        rows = read_scenes(ann, s["act"])
        pos = s["from"]
        for k in range(n):
            span = s["to"] - s["from"]
            pos = pos + rng.uniform(5, 40) if k and rng.random() < 0.4 else s["from"] + span * (k + rng.random()) / n
            start = round(min(pos, s["to"] - 5), 3)
            length = rng.choice([1, 2]) + 0.0
            sc = next((r[2] for r in rows if r[0] <= start <= r[1]), None)
            libretto = []
            if rng.random() < 0.4:
                libretto.append(dict(kind="direction", text=rng.choice(DIRECTIONS)))
            for _ in range(rng.choice([0, 1, 1, 2])):
                libretto.append(dict(kind="sung", person=rng.choice(SINGERS), text=rng.choice(LINES)))
            occurrences.append(dict(
                id=f"x{len(occurrences) + 1:02d}", act=s["act"], scene=sc, level=rng.choice([1, 2, 2, 3, 3, 3]),
                label=rng.choice(["[placeholder form A]", "[placeholder form B]", None]),
                note="[placeholder note on what is happening on stage]" if rng.random() < 0.6 else None,
                libretto=libretto, notation=dict(musicxml=musicxml(rng, int(length))),
                **{"from": start, "to": round(start + length + 0.5, 3)}))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(dict(
            format=1,
            motif=dict(id="sample", name="Sample",
                       description="Test fixture. Real section geometry from the Wagner Ring Dataset; every occurrence, text and note is made up."),
            levels=[dict(level=1, name="[placeholder level one]", description="[placeholder description of level one]"),
                    dict(level=2, name="[placeholder level two]", description="[placeholder description of level two]"),
                    dict(level=3, name="[placeholder level three]", description="[placeholder description of level three]")],
            sections=sections, occurrences=occurrences), f, ensure_ascii=False, indent=1)
    print(len(sections), "sections,", len(occurrences), "occurrences written to", args.out)


if __name__ == "__main__":
    main()
