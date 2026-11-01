#!/usr/bin/env bash
# Probe: do the second-highest voices of each hand ("inner voices") contain recurring material that the main streams miss?
# Runs the pipeline s01-s05 in a scratch work directory with only the inner streams, then e15 compares coverage.
set -euo pipefail
cd "$(dirname "$0")/../.."
export WAGNER_WORK=discovery/work_inner STREAMS=inner
mkdir -p $WAGNER_WORK
[ -e $WAGNER_WORK/notes ] || ln -s "$(pwd)/discovery/work/notes" $WAGNER_WORK/notes
PY=discovery/.venv/bin/python
$PY -I discovery/tools/s02_streams.py | tail -2
$PY -I discovery/tools/corpus.py
$PY -I discovery/tools/s03_seeds.py semi 22 | tail -1
$PY -I discovery/tools/s04_families.py semi | head -1
