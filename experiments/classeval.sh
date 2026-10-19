#!/bin/bash
# The forum on real code: all 70 ClassEval classes with at least 3 methods, private spec (an agent sees only
# the docstring of its own method), agent memory, 3 seeds. No posts; the report or the whole session as text;
# the shared KV stream. The items are the methods that call teammates' methods (86 per seed).
# One array task per (seed, condition): task t runs seed t / 4 and condition CONDITIONS[t % 4].
# Run from the repo root:  sbatch --array=0-11 experiments/classeval.sh
# Then:  python -m analysis.stats forum runs/classeval_<id>/*/*/
#SBATCH --job-name=lf-classeval
#SBATCH --time=10:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%A_%a.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
CONDITIONS=(
  "--channel none"
  "--channel text"
  "--channel text --source session"
  "--channel stream"
)
SEED=$((TASK_ID / 4))
python -m forum.run --backend hf --tasks classeval:all --n-agents 3 --rounds 8 --spec private --memory true \
    --probe false --seed "$SEED" ${CONDITIONS[$((TASK_ID % 4))]} --out "runs/classeval_${JOB_ID}/seed${SEED}"
