# Methodology — unsupervised discovery of leitmotifs in the Wagner Ring Dataset

Everything here is derived from the dataset's piano-reduction score (`data/01_RawData/score_musicxml`) plus the
score annotations (scenes, sung text) and the measure times of the Karajan1966 recording. No list of leitmotifs
was consulted. Every script is in `tools/` and numbered by step; the whole run is reproducible with
`tools/run_all.sh` (see `README.md`). Dead ends and probes are in `explore/`. Hand/agent judgments are files in
`decisions/`.

## 0. Disclosures (read these)
- The user ruled that nothing in `leitmotifs/` (an earlier, book-derived explorer) may be opened. Before that rule was
  given, one directory listing showed the *file names* of its 33 `definitions/*.json` files, and its `README.md`
  was read (it describes tooling, no melodies). No melody or occurrence data from it was ever seen or used.
- I (the model) know the Ring. I did not use that knowledge to seed searches or to choose thresholds. It does
  enter the review stage: agents and I read sung text and music and judge whether a candidate is thematic. This is
  a limit of "unsupervised" and is why the judgments are logged in `decisions/`.
- The user's criteria: >= 3 occurrences, **in >= 2 separate scenes** (scene = the annotated scenes of
  `ann_score_scenes`; 39 scenes in the cycle, e.g. act A has 4); >= 5 notes; similar rhythm *between the occurrences* (nothing about variety of durations inside a motif); any transposition.
  I count an *occurrence* as one statement: windows that overlap, or start within 4 quarter notes of each other,
  are merged, and the same melody seen in several streams is one occurrence (immediate repeats and sequences count once).

## 1. Representing the score (s01, s02, corpus.py)
- s01: MusicXML -> note table (measure, onset, duration, MIDI pitch, diatonic step, line = part/staff/voice). Ties
  merged, grace notes dropped. Measure numbers equal the annotation files' numbers (checked: counts match for all 11 acts).
- s02: the piano reduction is polyphonic but a melody is monophonic, so each act is cut into 8 monophonic **streams**:
  T1/T2 top note of the right/left hand, B1/B2 bottom note of each hand, and the top note of each of the 4 main voices
  (L111, L112, L211, L212). The skyline respects held notes (a lower new note under a sounding higher one is ignored).
  Repeated pitches are merged into one note (so tremolos and pulses count as one note — a known loss: motifs built
  on repeated notes can't be seen); a stream is cut at silences longer than 12 quarter notes.
  *Limitation:* a melody buried in the middle of chords (inner voice with no voice of its own) is invisible.
- corpus.py: all acts concatenated: 631,072 stream notes in 3,688 segments. Per note: semitone interval to the next
  note, diatonic-step interval (so that major and minor thirds match: "dint"), and a **rhythm class** — how long the
  note lasts (inter-onset interval) relative to the previous one: much shorter / shorter / same / longer / much
  longer (cut points 0.42, 0.73, 1.37, 2.4). Transposition-independent by construction (intervals only).

## 2. Finding recurring material (s03, s03b, s04)
- s03: all windows of n = 5..48 notes are hashed on (intervals, rhythm classes). A group of identical windows is a
  **seed** if it has >= 3 statements in >= 2 scenes, is **maximal** (no longer pattern has the same occurrences), and
  is *informative*: its information content (IC) under an order-2 Markov model of the corpus is >= 22 bits. IC is what
  removes trills, scale runs and arpeggio cells: they are predictable from their own first notes and cost few bits.
  Pitch-variety rules (first pass): `too_simple` rejected windows with < 3 distinct pitches, windows >= 85 % periodic with a
  cell shorter than 5 notes, and oscillations. **Removed after the user pointed out that the 5 notes need not have different
  pitches** (section 9): the seeds those rules had removed are mined apart (kinds `semi_simple`, `dint_simple`: the same
  procedure with the rules off, minus the seeds already found) so that the ids of the earlier candidates, which the reviewer
  verdicts refer to, stay valid. IC (the order-2 model) still keeps predictable patterns below the threshold.
- s03b (null model): surrogate corpora were sampled from the same order-2 Markov model with the real layout (times,
  scenes) and mined identically. Result (`results/null_model.tsv`, 3 surrogates): chance seeds fall from ~55 at n=5
  to 22 at n=8, 4 at n=10 and **0 for n >= 12**, while the score has 492, 502, 210 and 141+ seeds at those lengths.
  So long recurrences are not a statistical artifact; short ones (n <= 8) are partly chance, hence the
  length-dependent IC thresholds in s05b. (Caveat: real music has more local structure than the surrogate, so the
  null under-counts chance somewhat.)
- s04: seeds whose statements lie in the same places (>= 60 % of each one's statements overlap the other's, within
  1 quarter note) are linked into **families** ("when you see the same patterns coming up together, combine them").
  3,709 semitone seeds -> 1,400 families; 4,100 diatonic seeds -> 1,597 families.

## 3. Candidates and triage (s05, s05b, s06 ...)
- s05: unify both alphabets (a diatonic family is dropped if a semitone family covers it) -> 2,127 candidates, with
  descriptive features (length, IC, stepwise share, spread, streams, and rhythm uniformity / contrast, which are
  descriptive only: no step may select, rank, tag or show reviewers anything derived from them -- section 9).
- s05b: fragments folded into the longer candidate they sit inside (51); null-calibrated thresholds on IC and
  occurrences -> pool of 1,575 (see 3b).

### 3b. Calibrating the pool (null model, label predictability)
- explore/e10_null_by_ic.py: real vs surrogate seeds by IC bin. With >= 4 statements and IC >= 22 bits the surrogates
  give about 2 seeds against 100+ real (n = 5..9); with IC >= 24 and any statement count, <= 7 against >= 100. My first
  pool (IC 28-30 for short patterns) was far stricter than the null model requires; s05b now uses IC >= 24, or IC >= 22
  with >= 4 occurrences (the first, stricter pool had 669; the relaxed rule and the removal of the rhythm and pitch clauses give 1,575). Round 1
  (batches 01-06) reviewed the 669; round 2 (07-11) 458 more plus round 1's "unsure"; round 3 (12-16, blind to rhythm) re-reviewed
  everything not accepted and not already covered (section 9).
- explore/e12_label_predictability.py: the round 1-2 reviewers' M-versus-F labels were predicted from numeric features
  with cross-validated AUC 0.96, almost entirely by rhythmic uniformity. I first read that as "the criteria want long and
  short notes, so uniform patterns are figuration" and built rules on it. **That was wrong** (section 9): the dossiers
  carried my own "[figuration]/[motif]" tag, so the AUC measured the tag, and the criterion never asked for variety.
- explore/e18_null_by_rhythm_uniformity.py checks the information-content threshold itself for rhythm bias: at equal IC the
  surrogate music produces *fewer* uniform-rhythm seeds than varied-rhythm ones (about 2.5 against 20.5 at 24-26 bits), so
  the threshold is not too lenient for uniform patterns and needs no rhythm-specific treatment.
- Reviewers (sonnet agents, one batch each, ~110 blocks) wrote labels M/F/G/U, a 6-word theme and `same_as` ids.
  Their themes contain names they know; these are hints for the later naming task, not names.

### 3b'. Negative result: rhythm-agnostic mining
The user allows rhythm to vary between occurrences, but the exact miner compares 5-class rhythm tokens. To test whether
that hides motifs, `s03_seeds.py semi_nr` mines on intervals only. Its null model (`results/null_model_semi_nr.tsv`)
shows interval-only patterns are indistinguishable from chance below n = 12 (surrogates give as many or more seeds than the
score up to n = 11) and trustworthy only from n = 14. All 147 long (n >= 14) rhythm-agnostic families lie where existing
candidates already are (`explore/e13_nr_new_material.py`: 0 uncovered). So no new leitmotifs came from this pass; it is not
part of the pipeline. (Approximate rhythm variation is handled instead by s07_expand's rhythm tolerance.)

## 3c. Grouping (s07b, s07c)
- s07b: accepted (M) candidates are joined when a reviewer said `same_as` and the data agree (>= 34 % shared locations
  or a >= 75 % common run of intervals).
- s07_expand: approximate occurrences (<= 15 % interval mismatch, <= 25 % rhythm-class mismatch) of each group's
  pattern, kept only if surrogate corpora give <= 0.2 chance hits for the pattern.
- s07c: merge groups that "come up together" (>= 75 % of the smaller group's occurrences lie inside the other's: it has no
  life of its own) or that share a run of >= 6 intervals covering >= 85 % of the shorter pattern (variants). Merged groups
  keep every member pattern. 182 -> 134 groups on the first pass.

## 4. Results (corrected pass, 2026-11-01; see section 9 for what changed from the first pass)

Funnel (all numbers reproducible with `tools/run_all.sh`, about 50 seconds):

| Stage | Count |
|---|---|
| stream notes mined (8 streams x 11 acts) | 631,072 |
| seeds: maximal informative exact repeats, semitone / diatonic alphabet | 3,709 / 4,100 |
| families (seeds that come together) | 1,400 / 1,597 |
| candidates (both alphabets unified, diatonic ones already covered dropped) | 2,127 |
| roots after folding 51 fragments | 2,076 |
| candidates incl. 125 formerly pitch-filtered ones appended (ids 2127+) | 2,252 (roots 2,201) |
| pool above the null-calibrated thresholds (IC and occurrences only) | 1,575 |
| ... accepted M in rounds 1-2 (reviewers saw a rhythm tag; kept) | 564 |
| ... re-reviewed blind to rhythm in round 3 (earlier F 368, G 54, U 7, never reviewed 115) | 544 -> 438 M, 106 S (stock figure) |
| ... not reviewed in round 3: inside accepted occurrences, or repeating an accepted interval run | 360 |
| ... accepted by rule (never reviewed, formerly pitch-filtered, not already covered) | 78 |
| accepted M in total | 1,080 |
| groups after joining reviewer `same_as` pairs the data support | 854 |
| **leitmotifs after merging patterns that come together or are variants** | **670** |

The 670 (`results/INDEX.md`): 568 melodic, 67 scale-like and 35 repeated-cell patterns (arranged in three sections; nothing
is excluded by that); 5,327 occurrences, of which 360 are approximate matches added by `s07_expand.py`; 86 strong / 174
medium / 410 weak (statistical strength, not musical importance); 76 appear in all four operas; 155 have 10 or more notes
(longest 48). Every one has >= 3 occurrences in
>= 2 scenes and >= 5 notes (checked in `s08_build.py`, field `meets_criteria`). The other 626 roots are under the
null-calibrated IC thresholds (chance-level), so the search has reached the point where the statistics no longer separate
recurrence from chance. `results/excluded_stock.tsv` lists the 115 candidates excluded as stock figures (S) or generic
idioms (G).

### 4b. Saturation checks (does more searching find more?)
Three independent probes, each looking for material the main pipeline could have missed. All came back (almost) empty:
1. **Rhythm-agnostic mining** (`s03_seeds.py semi_nr`): 0 of 147 long families outside existing candidates (METHODOLOGY 3b').
2. **Inner voices** (`explore/e14`, `e15`): second-highest voice of each hand; 1 of 102 families new (5 notes, 3 occurrences).
3. **"Two exact + one varied" motifs** (`s10_pairs.py`): informative maximal repeats with only two exact statements
   (n >= 8, IC >= 26: 4,428 of them in the score, against about 260 in surrogate music) plus a third, approximate
   statement (<= 15 % interval, <= 25 % rhythm mismatch, <= 0.2 chance hits). 852 candidates pass, but they are almost
   all inside places already covered by earlier candidates: only 1 lies where no earlier candidate does
   (`explore/e16_pairs_novelty.py`; also 1 when the mistaken rhythm filter of the first version is removed). The same procedure on surrogate music gives 4-6 candidates.
Together with the null-calibrated floor (candidates below about 22 bits are not distinguishable from chance), this is why
I consider the search for this *kind* of leitmotif (melodic, monophonic-stream, recurring in similar rhythm) saturated.
Different kinds (chordal / harmonic, repeated-note motifs, orchestration) would need new representations.

## 5. Decisions you may want to revisit
1. **Occurrence = statement.** Windows that overlap or start within 4 quarter notes are one occurrence; the same melody
   in several streams is one. A motif sounded three times in a row counts once (user's "separate scenes" criterion is on top).
2. **Rhythm is only a matching rule.** Occurrences of a pattern must share its rhythm classes (exact in the miner, a
   tolerance in `s07_expand`). A pattern may have any durations, including all equal; nothing selects on variety.
3. **Scale-like patterns** (>= 60 % of the merged patterns are >= 85 % stepwise) are listed apart.
4. **Short patterns (5-7 notes)** are included when far above chance (IC >= 24 bits or >= 22 with >= 4 occurrences); most are
   `weak`. The user asked to favour long ones: sort by strength, then by length (INDEX does).
5. **Merging** (s07c) joins a group that lies inside another group's occurrences, so a leitmotif may contain several
   patterns (see `member_candidates`); the result can be coarser than a musicologist would want (e.g. one entry
   for a family of descending-scale variants with 147 occurrences). Split with a new rule in s07c if you prefer.
6. **Reviewers are language models** (sonnet) judging pitch shape, scenes and sung text. In round 3 they saw no durations and
   one rubric: exclude only *stock figures* (a bare one-direction scale run, a bare broken chord of one chord, a trill, a bare
   cadence formula); when in doubt include. The 115 exclusions are listed in `results/excluded_stock.tsv`.
   Rounds 1-2's M labels (564) were made while a rhythm tag and durations were visible; they were kept.
7. **No pitch-variety rules** (user's decision, section 9): few distinct pitches, short repeated cells, trills and oscillations
   are not rejected as such; they must still clear the IC threshold and the occurrence/scene rules. They are arranged in
   their own INDEX section ("Repeated-cell patterns"), which is presentation only.
8. **One semantic exclusion remains:** the 115 candidates in `results/excluded_stock.tsv` (106 labelled S "stock figure" by
   blind reviewers in round 3 -- bare scale run, bare broken chord of one chord, trill, bare cadence formula -- and 9 G from
   rounds 1-2). They meet the criteria; the exclusion is a judgement, not one of your criteria. To include them, treat label
   S/G as M in `s07b_group.py` and rerun; their reasons are in the file.

## 6. Limitations (what this method cannot see)
- **Harmonic / chordal motifs** (chorale-like themes, chord progressions) because streams are monophonic. Probably the
  biggest hole; a chord-sequence pass would need a different representation.
- **Repeated-note motifs** (repeated pitches are merged into one note).
- **Melodies inside chords**: probed with a second-voice stream (`explore/e14`, `e15`): negligible loss (1 of 102 families new).
- **Rhythm-agnostic variants**: probed, nothing new at n >= 14, and below that indistinguishable from chance.
- **Repeated pitches are merged into one note** (s02): "A A A A A" is one note, so motifs built on repeated pitches are not
  seen as such. This is the one remaining assumption about pitch variety; removing it changes every stream and candidate id.
- **Patterns under about 22 bits** (very short or common shapes) cannot be told from chance by this method.
- The piano reduction (Kleinmichel) sometimes simplifies or moves lines compared with the orchestral score, and its
  notes are spelled by a person, so enharmonic oddities (e.g. Fb for E) appear in the note names; intervals are unaffected.
- Scenes are the dataset's coarse annotations (39 in the cycle), so "two separate scenes" is a weak spread test; the
  JSON also gives acts and operas so you can require more.
- Times in recordings are interpolated from Karajan1966's manual measure times (about +-0.1 s at the measure).

## 7. For the naming step (next task)
Each `leitmotifs/LMnnn.md` lists every occurrence with the text sung there (a leading `~` = nearest text) and the act /
scene. `reviewer_themes` in the JSON are the reviewers' 6-word hints (they used what they know about the Ring: treat as
leads, not facts). A good first move: sort `occurrences.csv` by leitmotif and read the sung text of the strong ones.
No leitmotif has been named.

## 8. Cost and process notes
- 16 reviewer agents (sonnet), about 70-100k tokens each (mostly re-reading context across 3-6 tool calls), ~1.5M tokens
  in all; everything else is plain scripts (no model tokens). Round 3 (5 agents) existed only to undo the rhythm mistake.
- Bugs found and fixed on the way: the null-model scan read its pattern from the surrogate corpus (explore/e06); chain
  merging risk was checked (LM007 coverage is about 1 % of the score, so overlaps are not chance).
- Reproducibility: `tools/run_all.sh` rebuilt `results/` bit-for-bit identically (diff -r) from the committed decisions.

## 9. Correction: a misreading of the rhythm criterion (found by the user after the first pass)

**What the criterion says.** "Rhythms should be similar in each example ... the same pitches should be long while others
are always short" is about *consistency between occurrences* of one motif: the long notes stay long, the short ones short.

**What I did instead.** I read it as "a motif needs long and short notes" and built that assumption into the selection:
1. `s05_candidates.py` tiered candidates as "figuration" when >= 85 % of the durations were equal.
2. `s05b_reduce.py` dropped stepwise patterns with little duration contrast (57 candidates, 18 of them 14+ notes).
3. `s06_triage_inputs.py` showed reviewers the "[figuration]/[motif]" tag and a durations line, so their F labels followed it
   (AUC 0.96, which I misread as support for the rule).
4. `s06b_select_round2.py` did not send uniform-rhythm candidates to review; `s09` listed them apart and the results left them out.
5. I told you this "follows your criterion". It did not.
Effect: 330 uniform-rhythm pool candidates (225 labelled F, 105 never reviewed) and 57 stepwise ones were out; e.g. the
Rhinemaidens' wave cell (48 notes, 30 occurrences, all four operas) was missing. The first pass listed 313 leitmotifs.

**What I checked and what I changed.**
- Audited every step for rhythm-variety logic (`explore/e17`). The information-content threshold uses rhythm classes as
  one of its inputs, so I tested whether that biases against uniform patterns: it does not (`explore/e18`: at equal IC the
  surrogate music yields fewer uniform seeds than varied ones). Rhythm still enters the miner as the *matching* rule only.
- Removed the tier, the contrast clause, the tag and the durations from the dossiers, the round-2 skip, and the
  figuration list; moved the old scripts to `explore/*_HISTORICAL.py`; archived the round 1-2 dossiers that carried the tag
  (`decisions/archive_round1_2_dossiers/`).
- Round 3: re-reviewed, blind to rhythm and under one rubric, every pool candidate that was not accepted and not already
  covered (544): 438 are now leitmotifs, 106 are excluded as stock figures (listed with reasons).
- Rebuilt: 631 leitmotifs, 4,778 occurrences (first pass 313 / 2,718). `run_all.sh` reproduces the results identically.

**What is not fixed.** Rounds 1-2's accepted candidates (564) were judged with the tag visible; if that tag made some of
them look more thematic than they are, they stay in (an over-inclusive error, not an exclusion).

**Same mistake on the pitch side (second correction).** The miner also rejected windows with few distinct pitches, a short
repeated cell, or an oscillation, although the criterion says the 5 notes need not have different pitches. I measured it
(`explore/e20`: removing the rules adds ~3,650 seeds above threshold), asked, and the user chose to include them. Done:
`s03_seeds.py semi_simple|dint_simple` mine what the rules had removed; `s05_candidates.py` appends 125 new candidates
(those in places no existing candidate covers: 95 + 30), `s05b_reduce.py` loses its last pitch clause (pool 1,468 -> 1,575),
and `s06d_accept_pitch_variety.py` accepts by rule the 78 never-reviewed candidates that are not already inside accepted
leitmotifs (no reviewer judged them). Final: **670 leitmotifs, 5,327 occurrences** (631 / 4,778 before this step).
