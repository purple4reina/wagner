# Motif data format (version 1)

`index.html` shows one motif at a time. It reads one JSON file per motif.

- File: `motifs/<id>.json`
- URL: `index.html?motif=<id>`. The default `<id>` is `siegfried`.
- The browser blocks `fetch` on a page that it opens from disk. Serve this folder with `python3 -m http.server`.
- `motifs/sample.json` is a test file. Its sections come from the dataset. Every occurrence in it is made up.
- `motifs/index.json` is the list of motifs, `{ "motifs": [{ "id": "gold", "name": "Gold" }] }`. The page shows it as links down
  its left side, and marks the motif that is open. Without the file the page has no list. `tools/find_motif.py` writes it:
  one entry for each definition that has a motif file, in the order of the names.

The page ignores fields that this document does not list.

## Positions

Every position is a score position in the notation of the dataset's `ann_score_*` files:

- The number is a measure number. Numbering restarts in each act.
- The fraction is the position inside the measure. `142.750` is three quarters into measure 142.
- A range is half-open: `[from, to)`. The dataset ends ranges at `.999`. Add `0.001` to a dataset `measure_end` to get `to`.

## Top level

```json
{
  "format": 1,
  "motif": { "id": "siegfried", "name": "Siegfried", "description": "Optional. One sentence." },
  "levels": [ ],
  "sections": [ ],
  "occurrences": [ ]
}
```

`motif.name` appears in the page title. `motif.description` appears under the title.

## `levels`

A level tells how close an occurrence is to the original form of the motif. Level 0 is the original melody itself (see `original` under `sections`). Level 1 is the closest passage of the score. A higher number is farther away. The list is optional, and the builder of the data adds a level when it finds a new, farther group of occurrences.

```json
{ "level": 2, "name": "Same core pitches", "description": "One or two sentences that say what a level 2 occurrence has in common with the original." }
{ "level": 0, "label": "Original", "name": "The melody as given", "description": "The melody as you gave it. It is not a passage of the score." }
```

| Field | Type | Meaning |
|---|---|---|
| `level` | integer | The number of the level. |
| `label` | string, optional | The short name of the level. The default is `Level N`. |
| `name` | string, optional | What the level is. The page writes it after the label. |
| `description` | string, optional | One or two sentences. The page shows them under the name in the legend and in the tooltip of the level tag. |
| `hidden_by_default` | boolean, optional | When true, the page loads with the switch of this level off. The viewer can switch it on. The page ignores the flag if it would switch off every level, or if the link (`#id`) points to an occurrence of this level. |

When the data holds two or more levels, the page shows a legend with one switch for each level. Each switch hides or shows the marks of its level. A mark gets shorter and fainter as its level number grows, so level 0 has the tallest mark. The detail view names the level of the occurrence. A level that is missing from this list still works. The page calls it "Level N".

## `sections`

Sections are the segments of the ribbon, in story order. The page makes the width of each segment proportional to `to - from`. Both values count measures.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Unique name of the section. |
| `opera` | string | Opera title. Adjacent sections with the same title share one bracket and one color. It may be empty. The bracket then has a line and no title. |
| `act` | string | WorkID of the act, for example `WWV086B-2`. Occurrences refer to this value. |
| `label` | string | Full name, for example `Act 2`, `Prologue`, `Scene 3`. |
| `short` | string, optional | Name under the ribbon when `label` is too long for the segment, for example `Pro`. |
| `from`, `to` | number | Range of the section in the act. |
| `original` | boolean, optional | `true` marks the section of the original melody, which is not a part of the score. The page draws it in the accent color and does not count it when it gives colors to the operas. |

Use one section for each act. Use one section for each scene of *Das Rheingold*, because it has one act. Sections of one act must not overlap.

Take the values from the dataset as follows:

- `from` is the first `measure_start` in `ann_score_scenes` for the act. It is `0.888` for `WWV086B-2` and `WWV086B-3`, which start with a pickup measure.
- `to` is `floor(last measure_end) + 1`. For *Das Rheingold*, `to` of a scene is the `measure_start` of the next scene.

The original melody has its own section, with `original: true`. Put it first in the list, so that its mark sits to the left of the start of *Das Rheingold*. Its `act` is a name that no act of the score has, for example `ORIGINAL`. Its measures are not real, so choose the width that you want. About 4% of the total of the other sections is enough for a visible mark.

## `occurrences`

One entry for each use of the motif. The page draws a mark at `from`.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Unique and stable. The page puts it in the URL hash. |
| `level` | integer, optional | The level of the occurrence. The default is 1. |
| `act` | string | WorkID. A section with this `act` must contain `from`. The page skips an occurrence that fits no section and reports the count. |
| `from`, `to` | number | Range of the motif in the act. |
| `scene` | integer or null | Scene number from `ann_score_scenes` at `from`. The page shows nothing for `0` and null. It also shows nothing when the number repeats the section label, as in *Das Rheingold*. |
| `label` | string, optional | The form of the motif, for example `Horn call, second version`. The page shows it in italics and in the tooltip. |
| `note` | string, optional | One or two sentences that tell what happens in the story. |
| `libretto` | array or null | The text of this passage, in score order. See below. Use `[]` if there is none. Use `null` if no text applies, as for the original melody. The page then hides the text block. |
| `notation` | object or null | `{ "musicxml": "<string>", "svg": "<string>" }`. `svg` is optional. See below. |

### `libretto`

Each entry is one of:

```json
{ "kind": "sung", "person": "Siegfried", "text": "First line\nSecond line", "translation": "Optional English" }
{ "kind": "direction", "text": "Wagner's stage direction", "translation": "Optional English" }
```

`text` may contain `\n`. The page keeps the line breaks.

`translation` is optional. The page shows it under `text`, in a quieter style. The dataset has no translations. `tools/find_motif.py` reads `leitmotifs/translations.json`, which maps each German `text` to its English text, and prints each `text` that has no entry.

If the array has no `sung` entry, the page shows "Nobody sings during this passage." The page shows nothing if `libretto` is `null`.

Sources:

- `sung` entries come from the rows of `ann_score_singing` that overlap `[from, to)`.
- `direction` entries do not exist in the dataset. They come from Wagner's libretto. The builder of the data must align each direction to a measure.

### `notation`

`musicxml` is a complete, standalone MusicXML file in `score-partwise` form. It shows the motif as the piano score shows it:

- The notes are copies of the notes in `01_RawData/score_musicxml`. The clef, key signature, time signature, octave, rhythm, accidentals, stems, beams and ties are the ones of the score. A clef change inside the excerpt stays where the score has it.
- The file contains only the measures that the motif spans. The page breaks a long excerpt into lines.
- The file contains only the notes of the motif, in one staff, and the rests of that staff and voice between its first and its last note. It leaves out the other notes. The builder removes a beam, slur or tuplet bracket when the cut leaves it without a start or an end.

The page engraves the file with Verovio 4.3.1 from jsDelivr, so it needs an internet connection.

`svg` is optional. It is the text of an SVG file, for example an engraving that LilyPond made. If it is present, the page shows it in the notation panel instead of the Verovio engraving. In that case `musicxml` only drives the sound. Use it when the notation must look exactly as someone drew it. The page shows the SVG as an image with a `data:` URL. The code and the styles inside the SVG therefore cannot run or change the page. The image fills the width of the panel and is at most 420 pixels high. LilyPond draws black on a transparent background. In a dark color scheme the page inverts the image (`filter: invert(1)`), so that the notation is white on the dark panel. An SVG with other colors gets inverted colors in that scheme, so draw it in black.

The Play button needs no audio data. The page asks Verovio for a MIDI version of the same file and plays it with Web Audio. The page highlights each note while it sounds. An `svg` image has no note ids, so the page does not highlight a note then. The sound has the printed note values of the `musicxml` staff: a tie sounds as one note, and a repeated note sounds again. Verovio ignores a `time-modification` that has no tuplet bracket, so a note with such a marking sounds as long as its printed value, and not as long as its `<duration>`.

## Example

```json
{
  "format": 1,
  "motif": { "id": "example", "name": "Example" },
  "sections": [
    { "id": "A-1", "opera": "Das Rheingold", "act": "WWV086A", "label": "Scene 1", "short": "Sc 1", "from": 1, "to": 769 },
    { "id": "C-1", "opera": "Siegfried", "act": "WWV086C-1", "label": "Act 1", "from": 1, "to": 2984 }
  ],
  "occurrences": [
    {
      "id": "c1-0412",
      "act": "WWV086C-1",
      "scene": 1,
      "from": 412.5,
      "to": 414.5,
      "label": "[form of the motif]",
      "note": "[what happens in the story]",
      "libretto": [
        { "kind": "direction", "text": "[stage direction]" },
        { "kind": "sung", "person": "[character]", "text": "[sung text]" }
      ],
      "notation": { "musicxml": "<?xml version=\"1.0\"?><score-partwise>...</score-partwise>" }
    }
  ]
}
```

## Not in version 1

- Recordings. The sound on the page is a synthesized version of the notation. The positions are score measures, so a later step can find the time of any position in `ann_audio_measure` and play a recording.
- A match score for each occurrence. The page does not show how sure the builder of the data is.
