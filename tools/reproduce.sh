#!/bin/bash
# Rebuild every generated file of the leitmotif page, in order. To start from nothing, delete
# leitmotifs/motifs/*.json (and the dataset files that step 1 lists) and run this script.
#
#   1. fetch the dataset files that the finder reads (33 files, about 180 MB), if they are not on disk
#   2. find the passages of every leitmotif in leitmotifs/definitions, write leitmotifs/motifs/<id>.json
#   3. write the test file leitmotifs/motifs/sample.json
#
# Needs python3, and network access for step 1.
# The hand-written inputs are leitmotifs/definitions/*.json and leitmotifs/translations.json.
#
# usage: tools/reproduce.sh [DATA_DIR]      (the default is data)
set -euo pipefail
cd "$(dirname "$0")/.."
data="${1:-data}"

echo "== 1. the dataset in $data"
missing=0
for work in A B-1 B-2 B-3 C-1 C-2 C-3 D-0 D-1 D-2 D-3; do
  for file in "01_RawData/score_musicxml/Wagner_WWV086$work.xml" \
              "02_Annotations/ann_score_scenes/Wagner_WWV086$work.csv" \
              "02_Annotations/ann_score_singing/Wagner_WWV086$work.csv"; do
    [ -f "$data/$file" ] || missing=1
  done
done
if [ "$missing" = 1 ]; then
  python3 -I tools/fetch_from_zenodo.py --dest "$data" \
    --only 01_RawData/score_musicxml/ --only 02_Annotations/ann_score_scenes/ --only 02_Annotations/ann_score_singing/
else
  echo "all 33 files are on disk"
fi

echo "== 2. the passages of each leitmotif"
for definition in leitmotifs/definitions/*.json; do
  python3 -I tools/find_motif.py "$(basename "$definition" .json)" --data "$data"
done

echo "== 3. the test file"
python3 -I tools/make_sample.py --data "$data"
echo "done"
