# Motif data format (version 1)

`index.html` shows one motif at a time. It reads one JSON file per motif.

- File: `motifs/<id>.json`
- URL: `index.html?motif=<id>`. The default `<id>` is `siegfried`.
- The browser blocks `fetch` on a page that it opens from disk. Serve this folder with `python3 -m http.server`.
- `motifs/sample.json` is a test file. Its sections come from the dataset. Every occurrence in it is made up.

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
  "sections": [ ],
  "occurrences": [ ]
}
```

`motif.name` appears in the page title. `motif.description` appears under the title.

## `sections`

Sections are the segments of the ribbon, in story order. The page makes the width of each segment proportional to `to - from`. Both values count measures.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Unique name of the section. |
| `opera` | string | Opera title. Adjacent sections with the same title share one bracket and one color. |
| `act` | string | WorkID of the act, for example `WWV086B-2`. Occurrences refer to this value. |
| `label` | string | Full name, for example `Act 2`, `Prologue`, `Scene 3`. |
| `short` | string, optional | Name under the ribbon when `label` is too long for the segment, for example `Pro`. |
| `from`, `to` | number | Range of the section in the act. |

Use one section for each act. Use one section for each scene of *Das Rheingold*, because it has one act. Sections of one act must not overlap.

Take the values from the dataset as follows:

- `from` is the first `measure_start` in `ann_score_scenes` for the act. It is `0.888` for `WWV086B-2` and `WWV086B-3`, which start with a pickup measure.
- `to` is `floor(last measure_end) + 1`. For *Das Rheingold*, `to` of a scene is the `measure_start` of the next scene.

## `occurrences`

One entry for each use of the motif. The page draws a mark at `from`.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Unique and stable. The page puts it in the URL hash. |
| `act` | string | WorkID. A section with this `act` must contain `from`. The page skips an occurrence that fits no section and reports the count. |
| `from`, `to` | number | Range of the motif in the act. |
| `scene` | integer or null | Scene number from `ann_score_scenes` at `from`. The page shows nothing for `0` and null. It also shows nothing when the number repeats the section label, as in *Das Rheingold*. |
| `label` | string, optional | The form of the motif, for example `Horn call, second version`. The page shows it in italics and in the tooltip. |
| `note` | string, optional | One or two sentences that tell what happens in the story. |
| `libretto` | array | The text of this passage, in score order. See below. Use `[]` if there is none. |
| `notation` | object or null | `{ "musicxml": "<string>" }`. See below. |

### `libretto`

Each entry is one of:

```json
{ "kind": "sung", "person": "Siegfried", "text": "First line\nSecond line" }
{ "kind": "direction", "text": "Wagner's stage direction" }
```

`text` may contain `\n`. The page keeps the line breaks.

If the array has no `sung` entry, the page shows "Nobody sings during this passage."

Sources:

- `sung` entries come from the rows of `ann_score_singing` that overlap `[from, to)`.
- `direction` entries do not exist in the dataset. They come from Wagner's libretto. The builder of the data must align each direction to a measure.

### `notation`

`musicxml` is a complete, standalone MusicXML file in `score-partwise` form. It contains:

- only the measures that the motif spans (about four or fewer), and
- only the notes that belong to the motif. Other notes are removed or replaced with rests.

The first measure carries the clef, key signature and time signature. The excerpt may use one staff or two.

The page engraves the file with Verovio 4.3.1 from jsDelivr, so it needs an internet connection. Cut the excerpt from `01_RawData/score_musicxml`.

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

- Audio. The positions are score measures. A later step can find the time of any position in `ann_audio_measure`.
- A match score for each occurrence. The page does not show how sure the builder of the data is.
