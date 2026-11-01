# explore/ — probes that informed decisions

Not part of the pipeline; kept so the reasoning can be checked. Run from the project root with
`discovery/.venv/bin/python -I discovery/explore/<file>.py`. Some early ones use the first versions of the helpers.

| File | Question | Answer |
|---|---|---|
| `e01_repeat_counts.py` | How many exact repeated windows are there, by length? | Thousands even at n = 20; raw counts are inflated by the same melody in several streams and by overlapping windows. |
| `e02_clustered_counts.py` | Same, after merging windows into statements and using information content (IC) | Still thousands: most are trills, scales, arpeggio cells. Led to the order-2 Markov IC and the periodicity/oscillation filters in `s03_seeds.py`. |
| `e03_peek_groups.py`, `e04_family_table.py`, `e05_sample_candidates.py` | Look at samples by eye | Showed the generic-figuration problem and that motif-like material exists among the rest. |
| `e06_debug_null_hits.py` | Why did the null model give 335 chance hits for one pattern? | Bug: the pattern was read from the surrogate corpus instead of the real one (fixed in `s07_expand.py`). |
| `e07_show_group.py`, `e08_group_overlaps.py` | Inspect a group; find groups that are really one | 108 overlapping pairs before merging; led to `s07c_merge_groups.py`. |
| `e09_next_tier.py`, `e11_tier2_cover.py` | How many candidates did the first pool leave out; how many are already covered by accepted leitmotifs | 1458 left out; of the 742 added by the calibrated thresholds, 203 are covered. |
| `e10_null_by_ic.py` | Real vs chance seeds by IC bin, short patterns | IC >= 24, or >= 22 with >= 4 occurrences, is far above chance: the pool thresholds in `s05b_reduce.py`. |
| `e12_label_predictability.py` | Are the reviewers' M/F labels predictable from numbers? | Yes (AUC 0.96), almost only from rhythm uniformity: figuration by rule. |
| `e13_nr_new_material.py` | Does rhythm-agnostic mining find new long motifs? | No: 0 of 147 long families lie outside existing candidates. |
| `e14_inner_voice_probe.sh`, `e15_inner_voice_coverage.py` | Are there recurring melodies inside the chords (second voice of each hand)? | Practically no: 1 of 102 families is new (5 notes, 3 occurrences in one opera). |
| `ids_test.txt` | Test input for `s07_expand.py` | |
