# Leitmotif explorer

`index.html` shows every passage of the piano score of the Wagner Ring Dataset that matches a leitmotif, on a
timeline of the four operas. The format of the data is in `DATA-SPEC.md`.

## Open the page

Serve this folder. A browser blocks a page that it opens from disk from reading its data.

```
cd leitmotifs && python3 -m http.server
```

Then open `http://localhost:8000/` for the Siegfried motif, or `http://localhost:8000/?motif=sample` for the test file.
The list down the left side of the page shows every leitmotif that has been analyzed. Click one to open it, or press
the up and down arrow keys to go to the one above or below. The left and right arrow keys step through the
appearances of the open motif, and the space bar plays the notation. The "Full score" button under the notation shows and plays the whole piano
score of the same measures, with the notes of the leitmotif in purple.

## Rebuild all generated files

`motifs/*.json` are generated. Delete them and run:

```
tools/reproduce.sh
```

The script runs these steps in order. You can run each step alone.

| Step | Command | Result |
|---|---|---|
| 1. Fetch the dataset | `python3 -I tools/fetch_from_zenodo.py --only 01_RawData/score_musicxml/ --only 02_Annotations/ann_score_scenes/ --only 02_Annotations/ann_score_singing/ --only 02_Annotations/ann_audio_measure/` | 209 files in `data/` (about 185 MB). The script skips this step if the files are there. |
| 2. Find the passages | `python3 -I tools/find_motif.py siegfried` | `motifs/siegfried.json` and `motifs/siegfried.full.json` (the whole piano score of each passage). Passages that overlap, or lie within one measure of each other (`MERGE_GAP`), are one example, also across staves and voices. It has the level of the closest of them, and its notes are those of all of them. |
| 3. Link the leitmotifs | `python3 -I tools/link_motifs.py` | `motifs/also.json`: for each example, the other leitmotifs that have an example in its measures or the measure before or after (`REACH`). Run it again after any leitmotif changes. The page shows them under "Also present". |
| 4. Write the test file | `python3 -I tools/make_sample.py` | `motifs/sample.json` |

The hand-written inputs are `definitions/*.json`, `translations.json` and `order.json` (the ids that the sidebar lists first,
in the order of Holman's book; the other leitmotifs follow in alphabetical order). Nothing else is typed in.

## Add a leitmotif

1. Write `definitions/<id>.json`. It holds `id`, `name`, `lilypond` (the melody in absolute LilyPond notes; as in
   LilyPond, a note without a duration takes the duration of the note before it; rests, double dots, 32nd notes,
   double sharps and flats, and `\tuplet 2/3 { ... }` work, and any other text is an error),
   `core_notes` (the first and the last note, counted from 1, that levels 2 and 3 look for) and `original`
   (`octaves_up`, `time` and `partial`: how the page draws the melody; leave out `partial` if there is no pickup; add
   `"clef": "bass"` and `key_signature`, the number of sharps or minus the number of flats, if it does not have a
   treble clef and no key signature). Copy `definitions/siegfried.json`, or `definitions/gold.json` for a bass clef.
   Optional: `openings`, how many notes each "Opening, other keys" level keeps (the default is `[8, 6]`). Use fewer
   for a melody whose first notes are a common figure, such as a scale: `definitions/spear.json` has `[8]`.
   Optional: `max_level`, the farthest level to look for. A melody of fewer than about 9 notes finds mostly
   coincidences at levels 3 and 4 (and the search is slow), so `definitions/erda.json` has `2`.
   A rest of the melody is a gap in the score: level 1 needs the same rest, the other levels also accept none.
   Also `source`, the key of the book or other place that the melody comes from in `sources.json` (`"companion"`:
   Spencer and Millington, *Wagner's Ring of the Nibelung: A Companion*; `"holman"`: Holman, *Wagner's Ring: A
   Listener's Companion & Concordance*). The page shows it in the footer.
   Optional: `variant`, the letter of one form of a leitmotif that has several, such as (A) and (B) in Holman. Write one
   definition for each form, with the same `name` and a different `variant` (`definitions/valhalla-a.json`). The page
   names it "Valhalla (A)" and lists the forms under one heading "Valhalla" in the sidebar.
   A melody with chords or a second voice gives the top note of each chord, or the main voice: the finder follows one line.
2. For a leitmotif of Holman's book, add its id to `order.json`, at the place where it stands in the book.
   Run `python3 -I tools/find_motif.py <id>`. Open the page with `?motif=<id>`.
3. The finder lists each sung line that has no English. Add the English to `translations.json`, which all
   leitmotifs share, and run the finder again.

## The full transcription as the original

A definition keeps one melodic line, because the finder follows one line. For the leitmotifs of Holman's book, the user's whole
transcription (chords, second voice, slurs, dynamics) is in `sheetmusic/leitmotifs.ly`, which is not in this repository.
`python3 -I tools/engrave_originals.py` engraves each section of that file with LilyPond (it needs Docker) and writes
`originals/<id>.svg`. Then `python3 -I tools/find_motif.py <id> --refresh` puts the engraving into the original of the motif, and the
page shows it in place of the one-line engraving. The Play button still plays the melody line. `reproduce.sh` keeps the `originals/`
files, so it does not need Docker.

## Look for more levels

`python3 -I tools/analyze_levels.py siegfried` counts what each candidate for a new level would find, and how many
of those passages are chance. It does not write any file.
