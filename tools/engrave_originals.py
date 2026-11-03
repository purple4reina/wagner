"""Engrave the whole transcription of each Holman leitmotif, as the user wrote it, for the "Original" of the page.

The definitions in leitmotifs/definitions keep one melodic line, because the finder follows one line. The user's
transcription in sheetmusic/leitmotifs.ly has the chords, the second voice, the slurs and the dynamics. This script cuts
the section of each definition that has `"source": "holman"` out of that file (the section whose \\sectionLabel is the
name of the leitmotif, such as "Valhalla (A)"), engraves it with LilyPond with the layout of that file, and writes
leitmotifs/originals/<id>.svg. tools/find_motif.py puts that file into the original of the motif as `notation.svg`
(see leitmotifs/DATA-SPEC.md), so the page shows the full transcription. The sound still plays the melody line.

Needs Docker (the image jeandeaual/lilypond, the version of the .ly file) and the .ly file, which is not in this repository.
Then run `python3 -I tools/find_motif.py <id> --refresh` for each motif, to put the new engraving into its file.

usage: python3 -I tools/engrave_originals.py [--source FILE.ly] [--committed] [--only ID ...]
"""
import argparse, json, pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFINITIONS = ROOT / "leitmotifs" / "definitions"
OUT = ROOT / "leitmotifs" / "originals"
IMAGE = "jeandeaual/lilypond:latest"  # LilyPond 2.25.12, the \version of the .ly file


def closing(text, start):
    """Return the index after the } that closes the { at text[start]. Comments and strings are skipped."""
    depth, i = 0, start
    while i < len(text):
        c = text[i]
        if c == "%":
            i = text.find("\n", i) if text.find("\n", i) >= 0 else len(text)
            continue
        if c == '"':
            i = text.index('"', i + 1)
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("a { has no }")


def cut(text):
    """Return (layout block, the \\set lines that open the music, {label: section text without its \\sectionLabel})."""
    layout_at = text.index("\\layout", text.index("\\score"))
    layout = text[layout_at:closing(text, text.index("{", layout_at))]
    heads = list(re.finditer(r'\{\s*\\sectionLabel\s+"([^"]+)"', text))
    opening = text[text.index("{", text.index("\\transpose")) + 1:heads[0].start()]
    sets = "\n".join(l for l in opening.splitlines() if l.strip().startswith("\\set"))
    sections = {}
    for m in heads:
        body = text[m.start():closing(text, m.start())]
        sections[m.group(1)] = re.sub(r'\\sectionLabel\s+"[^"]+"', "", body, count=1)
    return layout, sets, sections


def full_name(d):  # the same as find_motif.full_name
    return f"{d['name']} ({d['variant']})" if "variant" in d else d["name"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", type=pathlib.Path, default=ROOT.parent / "sheetmusic" / "leitmotifs.ly")
    ap.add_argument("--only", nargs="*", default=[], help="ids of the definitions to engrave (default: every Holman one)")
    ap.add_argument("--committed", action="store_true", help="read the .ly file as it is in git HEAD, not from the working tree: only what is committed counts")
    args = ap.parse_args()
    source = args.source.resolve()
    text = (subprocess.run(["git", "-C", str(source.parent), "show", f"HEAD:./{source.name}"], capture_output=True, text=True, check=True).stdout
            if args.committed else source.read_text(encoding="utf-8"))
    layout, sets, sections = cut(text)
    OUT.mkdir(exist_ok=True)
    failed = []
    for path in sorted(DEFINITIONS.glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        if d.get("source") != "holman" or (args.only and d["id"] not in args.only):
            continue
        simple = lambda t: re.sub(r"[^a-z0-9()]", "", t.lower())  # "Love's" and "Loves'" are the same section
        label = next((k for k in sections if simple(k) == simple(full_name(d))), full_name(d))
        if label not in sections:
            print(f"{d['id']}: no section named {label!r} in {source.name}", file=sys.stderr)
            failed.append(d["id"])
            continue
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            (tmp / "common.ly").write_text((source.parent / "common.ly").read_text(encoding="utf-8"), encoding="utf-8")
            (tmp / "original.ly").write_text(
                '\\version "2.25.12"\n\\include "common.ly"\n\\header { tagline = ##f }\n\\paper { print-page-number = ##f }\n'
                f"\\score {{\n{layout}\n\\transpose c c {{\n{sets}\n{sections[label]}\n}}\n}}\n", encoding="utf-8")
            run = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp}:/app", "-w", "/app", IMAGE,
                                  "lilypond", "--svg", "-dcrop", "original.ly"], capture_output=True, text=True)
            svg = tmp / "original.cropped.svg"
            if run.returncode or not svg.exists():
                print(f"{d['id']}: LilyPond failed\n{run.stderr[-800:]}", file=sys.stderr)
                failed.append(d["id"])
                continue
            (OUT / f"{d['id']}.svg").write_text(svg.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"{d['id']}: {(OUT / (d['id'] + '.svg')).stat().st_size // 1024} KB")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
