# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local copy of the **Wagner Ring Dataset (WRD)**: a multi-modal, multi-version annotated dataset of Wagner's *Der Ring des Nibelungen* (4 operas, 11 acts, 21,939 measures, 16 commercial recordings, ~232 h). It is data, not a codebase: there is no build, lint or test step. The git repo tracks `CLAUDE.md`, `README.md`, `tools/` and `leitmotifs/` (an HTML explorer built on the dataset, see the last section); `data/` is gitignored. Almost all work is reading the CSV annotations and scores.

- Source: Zenodo record 7672157 (DOI 10.5281/zenodo.7672157), v1.0, file `WagnerRing_Public_zenodo_v0-1.zip` (10,557,603,204 bytes, md5 `27b7af7082ca721a8ff1fb5d04503f7a`).
- Paper: Weiß et al., *TISMIR* 6(1):135–149, 2023, DOI 10.5334/tismir.161. Record licence is CC BY 3.0. Cite the paper and DOI.
- Authors: Christof Weiß, Vlora Arifi-Müller, Michael Krause, Frank Zalkow, Stephanie Klauk, Rainer Kleinertz, Meinard Müller.

## What is and is not on disk

The dataset sits in `data/`; every dataset path below is relative to it.

Present: `01_RawData/score_*` (~340 MB), all of `02_Annotations/` (~138 MB), `03_ExtraMaterial/`.

**Missing: `01_RawData/audio_wav/`** (33 WAVs, 13.85 GB). The disk is nearly full, so audio was deliberately skipped. Do not download the whole zip and do not extract everything: the archive unzips to 14.3 GB and the zip plus its contents can never coexist here. Ask the user before fetching any audio, and check `df -h .` first.

To fetch specific audio files (HTTP range requests, only those members are downloaded; zip paths are kept, so files land in `data/01_RawData/audio_wav/`; the destination defaults to `data/` whatever the working directory, override with `--dest`):

```bash
python3 -I tools/fetch_from_zenodo.py --only Wagner_WWV086B-1_Furtwangler1953.wav   # one act
python3 -I tools/fetch_from_zenodo.py --only _Furtwangler1953.wav                    # one whole recording (~4.6 GB)
```

Only three recordings are public: `KeilberthFurtw1952`, `Furtwangler1953`, `Krauss1953` (22,050 Hz, 16-bit stereo WAV, one file per act). The other 13 exist only as annotations; the audio must be ripped from the user's own CDs (see `03_ExtraMaterial/README.md`).

## Layout

- `01_RawData/` – `score_pdf_IMSLP` (scan of Kleinmichel's piano reduction), `score_sibelius` (hand-corrected `.sib`), `score_pdf_sibelius`, `score_musicxml`, `score_midi` (constant tempo, no expressive modelling), `audio_wav`.
- `02_Annotations/` – `ann_score_*` (4 types × 11 acts) and `ann_audio_*` (6 types × 11 acts × 16 recordings = 176 files each). Types: `measure` (audio only), `note` (audio only), `singing`, `scenes`, `keysignatures`, `timesignatures`.
- `03_ExtraMaterial/` – two scripts (below), `overview_rawdata.csv` (recording metadata, MusicBrainz IDs, durations; multi-row header), `WWV086_Scene-Measures.csv`, `WWV-LorentzRingHarmonicStructure-Final.csv` (key structure per section, German headers), `RippedAudio/<PerformanceID>/<PerformanceID>.csv` (maps CD/track to act for the merge script).
- `../tools/fetch_from_zenodo.py` (outside `data/`, not part of the dataset) – the range-request fetcher above.

## Naming and IDs

The **act** is the unit everything is split by. Files are `Wagner_<WorkID>[_<PerformanceID>].<ext>`.

- WorkIDs (11 acts): `WWV086A` (Rheingold), `WWV086B-1/2/3` (Walküre), `WWV086C-1/2/3` (Siegfried), `WWV086D-0` (Götterdämmerung prologue), `WWV086D-1/2/3`. Short form: `A`, `B1`, `C2`, `D0`.
- PerformanceID = conductor surname + first recording year. Accents are dropped: `Bohm1967`, `Furtwangler1953`.
- The 16: KeilberthFurtw1952, Furtwangler1953, Krauss1953, Solti1958, Karajan1966, Bohm1967, Swarowsky1968, Boulez1980, Janowski1980, Levine1987, Haitink1988, Sawallisch1989, Barenboim1991, Neuhold1993, Weigle2010, Thielemann2011. (`KeilberthFurtw1952` is Keilberth for all but Walküre, which is Furtwängler.)
- `ann_score_*` files have no PerformanceID (`Wagner_WWV086B-1.csv`); `ann_audio_*` files do (`Wagner_WWV086B-1_Karajan1966.csv`).

## Annotation formats

All CSVs are UTF-8, **semicolon-separated**, with a header row. Text fields (`person`, `text`) are double-quoted.

| Dir | Columns |
|---|---|
| `ann_score_singing` | `measure_start;measure_end;person;text` |
| `ann_score_scenes` | `measure_start;measure_end;scene` |
| `ann_score_keysignatures` | `measure;key signature` (accidentals: -1 = one flat, 3 = three sharps) |
| `ann_score_timesignatures` | `measure;time signature` (e.g. `3/2`) |
| `ann_audio_measure` | `start;measure` (seconds at which each measure begins) |
| `ann_audio_note` | `start;end;pitch;pitchclass` (seconds; MIDI pitch; pitch mod 12) |
| `ann_audio_singing` | `start;end;person;text` (seconds) |
| `ann_audio_scenes` | `start;end;scene` |
| `ann_audio_keysignatures` / `_timesignatures` | `start;<signature>` |

Conventions that are easy to get wrong:

- **Score positions** are 1-based measure numbers with a 3-digit fraction, and numbering restarts in every act. Every measure has length 1 whatever its meter, so `142.750` is three quarters into measure 142. Region ends like `380.999` mean "just before 381.000".
- **`ann_audio_measure` is the time axis.** Every other `ann_audio_*` file was derived from the `ann_score_*` files by linear interpolation between these measure times, so it cannot show rubato inside a measure. The final row of every file has a fractional measure number (e.g. `1523.5`) and marks the end of the act.
- **Measure times are only manual for three recordings:** Karajan1966, Haitink1988, Barenboim1991 (about ±0.1 s). The other 13 were transferred automatically (about ±0.2 s for ~80% of measures). Do not treat them as equally reliable ground truth.
- **Notes come from the piano reduction's MIDI**, aligned within each measure. Octaves and doublings differ from the orchestral recordings, so use `pitchclass` rather than `pitch` when comparing with audio.
- Lyrics follow the score, not Wagner's text. Scene `0` is a prelude where one exists.

## Scripts in `03_ExtraMaterial/`

Both use paths relative to the dataset root, so run them from `data/` (`cd data && python3 -I 03_ExtraMaterial/<script>.py`), not from `03_ExtraMaterial/` or the project root.

- `create_ann_audio_from_ann_score.py` (needs numpy, pandas, scipy) regenerates `ann_audio_{singing,scenes,keysignatures,timesignatures}` from `ann_score_*` plus `ann_audio_measure`. It **overwrites the shipped files** in `02_Annotations/`.
- `merge_ripped_audio.py` (needs numpy, pandas, librosa, soundfile) concatenates CD rips into per-act WAVs in `01_RawData/audio_wav/`. It does not resample, so rips keep the CD sample rate and will not match the public 22.05 kHz files.

Run Python on dataset files with `python3 -I`, and run these scripts only after reading what they currently do.

## Leitmotif explorer (`leitmotifs/`)

`leitmotifs/index.html` shows the passages of the piano score that match a leitmotif, on a timeline of the four operas, with the notation, the sung text and a MIDI-style Play button. `leitmotifs/README.md` says how to open it, rebuild it and add a leitmotif. `leitmotifs/DATA-SPEC.md` is the format of the data.

Every file in `leitmotifs/motifs/` is generated. Never edit one by hand, and never make one in a throwaway: the user must be able to delete them and rebuild them with `tools/reproduce.sh`. The hand-written inputs are `leitmotifs/definitions/*.json` (one melody per leitmotif) and `leitmotifs/translations.json` (English for the sung German, shared by all leitmotifs). The searches serve every leitmotif, so a search or an analysis belongs in a script under `tools/` (`find_motif.py`, `make_sample.py`, `analyze_levels.py`), not in a scratch file.

Matching rules, in `tools/find_motif.py`: one staff and voice, tied notes merged, a run of repeated notes counts as one note, octave is ignored, and passages may overlap in time (two are one statement only if they end on the same note of the same line, or start and end together). Step 2 of the rebuild needs Docker, because LilyPond draws the original melody.
