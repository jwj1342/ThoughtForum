#!/bin/bash
# Offline SecretBench measurement of KV posts (model/kv_posts.py): the author's KV cache placed before the
# reader's prompt, whole (kv:full) or B entries per head (kv:snap:B, chosen by the report's attention).
# Compared with text and with the producer's code pasted as text (artifact). 40 projects per condition.
#   task 0: honest reports, the no-message floor, artifact, and a transplant per KV writer
#   task 1: omitted format (what leaks) and false format (follows what the author knows or what it says)
#   task 2: controls for every speech: the report plus the code as text (text_artifact, what kv:full holds),
#           and B entries chosen without the report: the last B (recent) or evenly spaced (uniform)
#   task 3: capacity: tags of 8 and 16 letters (about 43 and 80 bits)
#   task 4: the author's whole session pasted as a message (transcript: the content of kv:full, as text),
#           and the load setting with M = 1 post per reader
#   tasks 5, 6: load: M = 4 and 16 posts per reader, the producer's and M - 1 other projects'
#   tasks 7, 8: load, M = 4 and 16: the sessions as text (transcript), and whole kv posts with the shared
#           system turn kept once, end to end or at parallel positions
#   task 9: diagnostic, M = 4: the M sessions encoded together in one pass (joint) instead of one by one
# Task 0 also ran kv:recent:64 without the first 4 entries (attention sinks); task 2 replaces it.
# Run from the repo root:  sbatch --array=0-9 experiments/measure_kv.sh   or   TASK=1 bash experiments/measure_kv.sh
#SBATCH --job-name=lf-measure-kv
#SBATCH --time=03:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%A_%a.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
python -m unittest tests.test_backends
OUT="runs/measure_kv_${JOB_ID}"
M=(python -m benchmark.measure --n 40 --writer kv:full,kv:snap:64,kv:snap:256,kv:recent:64)
case "$TASK_ID" in
  0) "${M[@]}" --speech honest --channel none,text,artifact,kv --out "$OUT/honest" ;;
  1) "${M[@]}" --speech omit,lie --channel text,kv --out "$OUT/omit_lie" ;;
  2) python -m benchmark.measure --n 40 --writer kv:recent:64,kv:uniform:64,kv:uniform:256 \
         --channel text_artifact,kv --out "$OUT/controls" ;;
  3) for L in 8 16; do
       python -m benchmark.measure --n 40 --writer kv:full,kv:snap:64,kv:snap:256 --speech honest \
           --channel text,kv --tag-len "$L" --out "$OUT/capacity_$L"
     done ;;
  4) python -m benchmark.measure --n 40 --channel transcript --out "$OUT/transcript"
     L=(python -m benchmark.measure --n 40 --writer kv:full,kv:snap:256 --speech honest,lie --channel text,text_artifact,kv)
     "${L[@]}" --posts 1 --out "$OUT/load_1" ;;
  5|6) M=$([ "$TASK_ID" = 5 ] && echo 4 || echo 16)
     python -m benchmark.measure --n 40 --writer kv:full,kv:snap:256 --speech honest,lie --channel text,text_artifact,kv \
         --posts "$M" --out "$OUT/load_$M" ;;
  7|8) M=$([ "$TASK_ID" = 7 ] && echo 4 || echo 16)
     L=(python -m benchmark.measure --n 40 --writer kv:full --speech honest,lie --posts "$M")
     "${L[@]}" --channel transcript --out "$OUT/load_${M}_transcript"
     "${L[@]}" --channel kv --dedup --out "$OUT/load_${M}_dedup"
     "${L[@]}" --channel kv --dedup --layout parallel --out "$OUT/load_${M}_parallel" ;;
  9) python -m benchmark.measure --n 40 --writer kv:full --speech honest,lie --posts 4 --channel kv --joint \
         --out "$OUT/load_4_joint" ;;
esac
