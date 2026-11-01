#!/usr/bin/env bash
# Runs every automated step of the discovery in order. Run from anywhere. About 5 minutes.
# Judgment steps (decisions/*.tsv) are inputs: see README.md. Steps after s06 are appended as they are written.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=discovery/.venv/bin/python
if [ ! -x "$PY" ]; then
  python3 -m venv discovery/.venv
  discovery/.venv/bin/pip install -q -r discovery/requirements.txt
fi
run() { echo "== $*"; "$PY" -I discovery/tools/"$@"; }
run s01_parse_score.py
run s02_streams.py
run corpus.py
run s03_seeds.py semi 22
run s03_seeds.py dint 22
run s03b_null.py 3 22
# seeds the old pitch-variety rules removed (kept apart so earlier candidate ids stay valid; see s03_seeds.py)
run s03_seeds.py semi_simple 22
run s03_seeds.py dint_simple 22
run s04_families.py semi
run s04_families.py dint
run s04_families.py semi_simple
run s04_families.py dint_simple
run s05_candidates.py
run s05b_reduce.py
# Review rounds 1-3: the verdicts are the committed decisions/triage_batch_*.tsv. Round 3 (batches 12+) is the one a human
# would redo: it reads blind dossiers of the candidates listed in decisions/round3_ids.txt. (Rounds 1-2 dossiers are archived
# in decisions/archive_round1_2_dossiers/; they carried a rhythm-uniformity tag, a mistake corrected by round 3.)
run s06_triage_inputs.py 120 discovery/decisions/round3_ids.txt 12 4
# Everything below uses the committed verdicts and ids (decisions/: triage_batch_*.tsv from reviewers, rule_pitch_variety.tsv
# from s06d, a one-off). round1-3 ids, s06c and s06d are one-offs and are not rerun here.
run s07b_group.py
run s07_expand.py discovery/work/accepted_ids.txt
run s07c_merge_groups.py
run s08_build.py
run s09_excluded_list.py
