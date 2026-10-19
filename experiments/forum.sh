#!/bin/bash
# The multi-agent forum (forum/run.py) on SecretBench: 120 projects, 3 agents, private spec, agent memory,
# 3 seeds. Honest authors: no posts; the report, the code, or the whole session as text; soft-token latent
# posts; the shared KV stream, and the stream with shuffled segments. Every author misstating its formats
# (mislead): the report, the code, the session, the stream.
# One array task per (seed, condition): task t runs seed t / 11 and condition CONDITIONS[t % 11].
# Run from the repo root:  sbatch --array=0-32 experiments/forum.sh
# Then:  python -m analysis.stats forum runs/forum_<id>/*/honest/*/   (and .../mislead/*/)
#SBATCH --job-name=lf-forum
#SBATCH --time=10:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%A_%a.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
CONDITIONS=(
  "honest  --channel none"
  "honest  --channel text"
  "honest  --channel text --source artifact"
  "honest  --channel text --source session"
  "honest  --channel latent --writer-head random:16"
  "honest  --channel stream"
  "honest  --channel stream --control shuffle"
  "mislead --channel text"
  "mislead --channel text --source artifact"
  "mislead --channel text --source session"
  "mislead --channel stream"
)
SEED=$((TASK_ID / 11))
read -r SETTING ARGS <<< "${CONDITIONS[$((TASK_ID % 11))]}"
LIE=()
[ "$SETTING" = mislead ] && LIE=(--overclaim-frac 1.0 --overclaim-mode mislead)
python -m forum.run --backend hf --tasks secret:120 --n-agents 3 --rounds 8 --spec private --memory true \
    --probe false --seed "$SEED" "${LIE[@]}" $ARGS --out "runs/forum_${JOB_ID}/seed${SEED}/${SETTING}"
