# Leitmotif explorer

`index.html` shows every passage of the piano score of the Wagner Ring Dataset that matches a leitmotif, on a
timeline of the four operas. The format of the data is in `DATA-SPEC.md`.

## Open the page

Serve this folder. A browser blocks a page that it opens from disk from reading its data.

```
cd leitmotifs && python3 -m http.server
```

Then open `http://localhost:8000/` for the Siegfried motif, or `http://localhost:8000/?motif=sample` for the test file.

## Rebuild all generated files

`motifs/*.json` are generated. Delete them and run:

```
tools/reproduce.sh
```

The script runs these steps in order. You can run each step alone.

| Step | Command | Result |
|---|---|---|
| 1. Fetch the dataset | `python3 -I tools/fetch_from_zenodo.py --only 01_RawData/score_musicxml/ --only 02_Annotations/ann_score_scenes/ --only 02_Annotations/ann_score_singing/` | 33 files in `data/` (about 180 MB). The script skips this step if the files are there. |
| 2. Find the passages | `python3 -I tools/find_motif.py siegfried` | `motifs/siegfried.json` |
| 3. Write the test file | `python3 -I tools/make_sample.py` | `motifs/sample.json` |

The hand-written inputs are `definitions/*.json` and `translations.json`. Nothing else is typed in.

## Add a leitmotif

1. Write `definitions/<id>.json`. It holds `id`, `name`, `lilypond` (the melody in absolute LilyPond notes),
   `core_notes` (the first and the last note, counted from 1, that levels 2 and 3 look for) and `original`
   (`octaves_up`, `time` and `partial`: how the page draws the melody). Copy `definitions/siegfried.json`.
2. Run `python3 -I tools/find_motif.py <id>`. Open the page with `?motif=<id>`.
3. The finder lists each sung line that has no English. Add the English to `translations.json`, which all
   leitmotifs share, and run the finder again.

## Look for more levels

`python3 -I tools/analyze_levels.py siegfried` counts what each candidate for a new level would find, and how many
of those passages are chance. It does not write any file.
