#!/bin/bash
# E0st: the shared KV stream (channel=stream, model/kv_posts.py KVStream) in the SecretBench forum.
# Each post is the author's session encoded on top of all posts before it; readers generate after the
# segments of the posts they get. Same setting as E0s3 / E0s4 (40 projects, 3 agents, private spec, memory).
#   task 0: honest authors: stream, stream with shuffled segments, text report
#   task 1: every author misstates its method's format (mislead): stream, text report
#   task 2: the text version of a stream post (source=session: the author's whole session as text), honest and mislead
# Run from the repo root:  sbatch --array=0-2 experiments/e0st.sh
#SBATCH --job-name=lf-e0st
#SBATCH --time=05:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%A_%a.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
python -m unittest tests.test_backends tests.test_forum
OUT="runs/e0st_${JOB_ID}"
COMMON=(--backend hf --tasks secret:40 --n-agents 3 --rounds 8 --spec private --memory true --probe false)
case "$TASK_ID" in
  0) python -m forum.run "${COMMON[@]}" --channel stream --grid control=none,shuffle --out "$OUT/honest"
     python -m forum.run "${COMMON[@]}" --channel text --out "$OUT/honest" ;;
  1) M=(--overclaim-frac 1.0 --overclaim-mode mislead)
     python -m forum.run "${COMMON[@]}" "${M[@]}" --channel stream --out "$OUT/mislead"
     python -m forum.run "${COMMON[@]}" "${M[@]}" --channel text --out "$OUT/mislead" ;;
  2) python -m forum.run "${COMMON[@]}" --channel text --source session --out "$OUT/honest"
     python -m forum.run "${COMMON[@]}" --overclaim-frac 1.0 --overclaim-mode mislead --channel text --source session \
         --out "$OUT/mislead" ;;
esac
