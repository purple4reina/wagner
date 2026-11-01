"""Write leitmotifs/motifs/also.json: for each example of each leitmotif, the other leitmotifs that have an example nearby.

Run it after tools/find_motif.py has written the motif files, because it reads all of them. The page cannot load every motif
file to find this out, so it reads the small file that this script writes.

An example is nearby when it is in the same act and touches the measures that the page shows for the first example, or the
REACH measures before or after them. Only the examples that the timeline of their own leitmotif shows at the start count:
a level that the file marks "hidden_by_default" is left out, as the page leaves it out. For each other leitmotif the file
keeps the closest example, so a leitmotif is listed once.

usage: python3 -I tools/link_motifs.py [--out FILE]
"""
import argparse, json, math, pathlib
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parent.parent
MOTIFS = ROOT / "leitmotifs" / "motifs"
REACH = 1  # the measures before and after an example in which another leitmotif counts


def read(motif):
    """Return the examples of `motif` (an entry of index.json), without the original melody, each with the measures that the
    page shows for it (first and last), its level and the name of the level, and whether the timeline shows it at the start."""
    data = json.loads((MOTIFS / f"{motif['id']}.json").read_text(encoding="utf-8"))
    names = {l["level"]: l.get("name") or f"Level {l['level']}" for l in data.get("levels", [])}
    original = {s["act"] for s in data["sections"] if s.get("original")}
    examples = [SimpleNamespace(motif=motif["id"], name=motif["name"], id=o["id"], act=o["act"], level=o.get("level", 1),
                                closeness=names.get(o.get("level", 1), f"Level {o.get('level', 1)}"), start=o["from"],
                                first=math.floor(o["from"]), last=math.ceil(o["to"]) - 1)
                for o in data["occurrences"] if o["act"] not in original]
    off = {l["level"] for l in data.get("levels", []) if l.get("hidden_by_default")} & {e.level for e in examples}
    if off == {e.level for e in examples}:  # the page keeps one level on
        off = set()
    for e in examples:
        e.shown = e.level not in off
    return examples


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=pathlib.Path, default=MOTIFS / "also.json")
    args = ap.parse_args()
    listing = json.loads((MOTIFS / "index.json").read_text(encoding="utf-8"))["motifs"]
    everything = [e for motif in listing for e in read(motif)]

    also, count = {}, 0
    for mine in everything:
        near = {}  # the closest example of each other leitmotif
        for other in everything:
            if other.motif == mine.motif or not other.shown or other.act != mine.act:
                continue
            if other.first <= mine.last + REACH and other.last >= mine.first - REACH:
                key = (other.level, abs(other.start - mine.start), other.name)
                if other.motif not in near or key < near[other.motif][0]:
                    near[other.motif] = (key, other)
        if near:
            count += 1
            also.setdefault(mine.motif, {})[mine.id] = [
                dict(motif=o.motif, name=o.name, id=o.id, level=o.level, closeness=o.closeness) for _, o in sorted(near.values(), key=lambda p: p[0])]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(dict(format=1, also=also), f, ensure_ascii=False, separators=(",", ":"))
    print(f"{count} of {len(everything)} examples have another leitmotif within {REACH} measure{'' if REACH == 1 else 's'}; written to {args.out}")


if __name__ == "__main__":
    main()
