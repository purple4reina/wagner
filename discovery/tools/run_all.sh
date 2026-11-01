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
run s04_families.py semi
run s04_families.py dint
run s05_candidates.py
run s05b_reduce.py
# Review round 1 and 2: the dossiers below were read by reviewers, whose verdicts are the committed decisions/triage_batch_*.tsv
run s06_triage_inputs.py 112 discovery/decisions/round1_ids.txt 1 5
run s06_triage_inputs.py 110 discovery/decisions/round2_ids.txt 7 4
# Everything below uses the committed verdicts and ids (decisions/)
run s07b_group.py
run s07_expand.py discovery/work/accepted_ids.txt
run s07c_merge_groups.py
run s08_build.py
run s09_figuration_list.py
