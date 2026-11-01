# STATE — read this first when resuming

Task (from the user, 2026-11-01): discover leitmotifs in the Wagner Ring Dataset *on our own* from the piano-reduction
score. Criteria for each leitmotif: >= 3 occurrences, **in >= 2 separate scenes**; >= 5 distinct notes; similar
rhythm between the occurrences of a match (same notes long, same notes short); any transposition. Favour long motifs; merge patterns that always occur
together. Per leitmotif record every occurrence and the sung text. Naming the motifs is a LATER task, not this one.
Expected effort 12-24 h. Keep METHODOLOGY.md current (decisions, what was learned).

## Hard rules from the user
- **Rhythm criterion = consistency BETWEEN occurrences, not variety INSIDE a motif.** A uniform-rhythm pattern (all notes
  equal) is as valid as a dotted one. Never filter, tier, rank, tag or show reviewers anything derived from rhythmic
  variety/uniformity (descriptive columns are fine). I got this wrong once (METHODOLOGY section 9); the user corrected it.
- **Never open anything in `leitmotifs/`** (the old explorer: definitions, motifs, README, DATA-SPEC). Not even to peek.
  (Disclosure: before this rule was given, one `ls` showed the 33 file names in `leitmotifs/definitions/` and
  `leitmotifs/README.md` was read. No melodies were seen. Recorded in METHODOLOGY.md.)
- Do not look up leitmotif lists online. Derive everything from the data.
- Every script that produced a result is kept in `discovery/tools/` (or `discovery/explore/` for dead ends) so a human
  can reproduce it without an AI. Scripts are numbered by step. Hand decisions live in `discovery/decisions/` as files.
- Subagents are allowed ("go to town") but keep token use LOW: scripts first, agents only for musical judgment on
  compact dossiers; have agents write verdicts to disk and return one line.
- Do not `git commit` unless told to. `data/` and `discovery/work/`, `discovery/.venv/` are gitignored.
- Disk is nearly full (about 8 GB free). No audio is needed for this task.

## Environment
`cd discovery && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`. Run scripts from the project root:
`discovery/.venv/bin/python -I discovery/tools/<script>.py`.

## Progress log (newest last)
- [done] s01_parse_score.py -> work/notes/<act>.npz (366k notes, measure numbers match the annotations)
- [done] s02_streams.py -> work/streams/<act>.npz (8 monophonic views per act: T1 T2 B1 B2 L111 L112 L211 L212)
- [done] corpus.py (build work/corpus.npz), mine.py (hashing, order-2 Markov IC, clustering), s03_seeds.py <semi|dint>,
  s03b_null.py (null model -> results/null_model.tsv), s04_families.py <kind>, s05_candidates.py, s05b_reduce.py
  -> work/pool.pkl = 669 candidates to review (details and numbers: METHODOLOGY.md sections 1-3)
- [done] s06_triage_inputs.py -> work/triage/batch_01..06.txt (669 candidates, ~112 per batch)
- [done] 6 sonnet agents reviewed the 669-pool -> decisions/triage_batch_01..06.tsv: M=307 F=274 G=5 U=83.
  (reviewer `theme` columns contain names the reviewers know; they are hints for the later naming task, not names)
- [done] s07b_group.py (verdicts -> decisions/groups_unmerged.tsv; M only, same_as + data check), s07_expand.py
  (approximate matches, null-guarded: work/expansions.pkl), s07c_merge_groups.py (attach/variant merges ->
  decisions/groups_auto.tsv, merge_log.txt), s08_build.py -> results/INDEX.md, results/leitmotifs/LMnnn.{md,json},
  results/occurrences.csv. First full result: 134 leitmotifs (every one >= 3 occurrences in >= 2 scenes).
- Pipeline order: s07b -> s07_expand discovery/work/accepted_ids.txt -> s07c -> s08. (run_all.sh does s01..s06 only so far)
- [done] calibration (explore/e10): seeds with IC >= 24, or IC >= 22 with >= 4 occurrences, are essentially never chance
  -> s05b_reduce.py relaxed (pool 669 -> 1411; pool_v1.pkl keeps round 1's pool). explore/e12: reviewers' M/F labels are
  predicted by rhythm uniformity alone (CV AUC 0.96) => rule: uniform-rhythm (>=85 % one duration) = "figuration",
  excluded from the leitmotif list by the user's own long/short-note criterion; only contrasting-rhythm candidates reviewed.
- [done] round 2 reviewed (batches 07-11: M=257 F=217 G=58 U=9). Verdict totals over 11 batches: M=564 F=491 G=63 U=9.
  Chain s07b -> s07_expand -> s07c -> s08 rerun: 313 leitmotifs (2718 occurrences): 291 melodic + 22 scalar;
  strength strong 45 / medium 110 / weak 158 (weak = short/rare but far above chance). Every one meets the criteria.
- [done] negative result: rhythm-agnostic (semi_nr) mining adds nothing (METHODOLOGY 3b'); figuration list
  (s09 -> results/figuration.tsv); results/FORMAT.md documents the outputs; run_all.sh covers the whole chain.
- [done] determinism: `tools/run_all.sh` (43 s) rebuilds results/ bit-for-bit identically (diff -r) from decisions/.
- [done] saturation probes: semi_nr, inner voices, 2-exact+1-varied (s10_pairs.py): nothing new (METHODOLOGY 4b).
- [done] docs: README.md (how to reproduce), METHODOLOGY.md (all decisions, funnel, limits, naming notes), results/FORMAT.md,
  explore/README.md (index of probes).

- [done 2026-11-01, after the user's correction] rhythm-variety assumptions removed (METHODOLOGY section 9): tier, contrast
  clause, reviewer tag/durations, round-2 skip, figuration list. s06c_select_round3.py -> decisions/round3_ids.txt (544);
  5 blind sonnet agents -> decisions/triage_batch_12..16.tsv (labels M include / S stock figure; 438 M, 106 S). Chain rerun.
  explore/e17 (audit), e18 (IC threshold is rhythm-neutral), e20 (pitch-variety filters), e16 rerun.

- [done 2026-11-01, second correction] pitch-variety rules removed at the user's request ("not necessarily different pitches"):
  s03 kinds semi_simple/dint_simple (+ s04, s05 appends 125 candidates with ids >= 2127, earlier ids unchanged), s05b pitch
  clause gone, s06d_accept_pitch_variety.py -> decisions/rule_pitch_variety.tsv (78 accepted by rule), s08 adds a "cell" INDEX
  section (presentation only). run_all.sh extended; results rebuilt and reproduced identically (1 min 12 s).

## STATUS: complete pass finished (2026-11-01). 670 leitmotifs (568 melodic + 67 scalar + 35 repeated-cell), 5327 occurrences.
`tools/run_all.sh` rebuilds results/ and decisions/groups_* identically. Committed in git (see `git log`).

## If you continue (optional, in order of expected value)
0. Remaining judgement calls the user may want to flip: (a) the 115 stock-figure/generic exclusions (results/excluded_stock.tsv;
   treat S/G as M in s07b_group.py to include them), (b) repeated pitches are merged into one note in s02 (the one remaining
   pitch-variety assumption; changing it renumbers every candidate id, so decisions/ would have to be re-keyed).
1. Naming step (user's next task): see METHODOLOGY section 7. Several entries share dramatic hints (e.g. 3 entries mention
   the Valkyrie call, 2 Wotan's farewell, 2 Rhine) and may be merged by a human once named.
2. Harmonic / chordal motifs (METHODOLOGY section 6: the biggest known hole) need a new representation (chord roots +
   qualities per beat); build it as a separate pipeline in a new directory so existing candidate ids stay valid.
3. Repeated-note motifs (merged into one note now).
4. Tighten merges in s07c (ATTACH/COVER constants) if a human finds entries too coarse (LM007 is a family of descending
   scale variants with 147 occurrences).
Rules still apply: never open leitmotifs/; keep token use low; log every script; no commits unless asked.
