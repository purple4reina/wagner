# Leitmotif discovery — how to reproduce it without an AI

This directory holds an unsupervised search for recurring melodic material ("leitmotifs") in the piano-reduction score
of the Wagner Ring Dataset. `METHODOLOGY.md` explains what was done and why; `STATE.md` is the working log;
this file says how to run it.

## What you need
- The dataset in `../data/` (scores `01_RawData/score_musicxml` and annotations `02_Annotations/`; see `../CLAUDE.md`).
- Python 3 and the packages in `requirements.txt` (numpy, scipy, pandas, numba; scikit-learn only for `explore/e12`). From the project root:
  `python3 -m venv discovery/.venv && discovery/.venv/bin/pip install -r discovery/requirements.txt`
- About 20 MB of disk for `work/` (regenerable, not tracked in git).

## Run
`discovery/tools/run_all.sh` runs every automated step in order (about 45 seconds). Each script is also runnable alone:
`discovery/.venv/bin/python -I discovery/tools/<script>.py [args]` from the project root. Scripts are numbered; each one
reads what the earlier ones wrote to `work/` and says so in its docstring.

| Step | Script | Does |
|---|---|---|
| 1 | `s01_parse_score.py` | MusicXML -> note tables (`work/notes`) |
| 2 | `s02_streams.py` | monophonic streams (skyline / baseline / single voices) (`work/streams`) |
| 3 | `corpus.py` | whole-cycle corpus with interval and rhythm-class tokens (`work/corpus.npz`) |
| 4 | `s03_seeds.py <kind>` | maximal exact repeats that are informative: "seeds" (kinds: `semi`, `dint`, `semi_nr`) |
| 5 | `s03b_null.py` | null model: seeds expected by chance in surrogate music (`results/null_model.tsv`) |
| 6 | `s04_families.py <kind>` | seeds that come together -> families |
| 7 | `s05_candidates.py`, `s05b_reduce.py` | candidates, features, fragments folded, review pool |
| 8 | `s06_triage_inputs.py` | dossier text of the pool in batches (`work/triage/batch_NN.txt`); `s06b_select_round2.py` chose round 2 |
| 9 | `s07b_group.py`, `s07_expand.py`, `s07c_merge_groups.py` | verdicts -> groups, approximate occurrences, merges |
| 10 | `s08_build.py`, `s09_figuration_list.py` | `results/` |
| check | `s10_pairs.py [--null]` | saturation probe: 2 exact + 1 varied statements (not in `run_all.sh`; about 1 minute) |

## The judgment steps (done by AI reviewers, kept as files)
Statistics cannot tell a theme from accompaniment figuration. Steps after 8 need a musical reader:
read `work/triage/batch_NN.txt` and write `decisions/triage_batch_NN.tsv` (columns `id label theme same_as`; label
M = thematic motif, F = figuration, G = generic idiom, U = unsure). The files used for the published results are in
`decisions/` (`round1_ids.txt` and `round2_ids.txt` say which candidates each round reviewed), so `run_all.sh` runs
straight through on them; to use your own judgments, replace the `triage_batch_*.tsv` files.

## Results
`results/INDEX.md` lists every leitmotif found. `results/leitmotifs/LMnnn.md|json` hold every occurrence with act,
scene, measure range, streams, time in the Karajan1966 recording, the notes, and the text sung there.

## Scratch work
`explore/` holds probes that informed decisions (thresholds, bugs, dead ends). They are not needed to reproduce results.
