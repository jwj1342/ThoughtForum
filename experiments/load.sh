#!/bin/bash
# Many posts at once (benchmark/measure.py --load M): every reader gets M posts, those of its own
# producers and of other projects, in a random order. Can it pick out and combine the right ones?
# 200 SecretBench projects, seed 0, honest and lying authors; M = 2, 4, 8 (the class names stay distinct).
# One array task per (M, channel): task t runs M = LOADS[t / 4] and channel CHANNELS[t % 4].
# Run from the repo root:  sbatch --array=0-11 experiments/load.sh
# Then:  python -m analysis.stats measure "runs/load_<id>/*/rows.jsonl"
#SBATCH --job-name=lf-load
#SBATCH --time=10:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%A_%a.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
LOADS=(2 4 8)
CHANNELS=(text session kv stream)
M=${LOADS[$((TASK_ID / 4))]}
CH=${CHANNELS[$((TASK_ID % 4))]}
python -m benchmark.measure --n 200 --seed 0 --load "$M" --speech honest,lie --channel "$CH" \
    --out "runs/load_${JOB_ID}/load${M}_${CH}"
