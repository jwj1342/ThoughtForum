#!/bin/bash
# Offline measurement (benchmark/measure.py): what posts carry from their authors to a frozen reader.
# 200 SecretBench projects (1000 consumer items), 3 sampling seeds; every channel under every speech
# (honest / omit / lie), with the transplant control for the latent channels.
# One array task per (seed, channel): task t runs seed t / 7 and channel CHANNELS[t % 7].
# Run from the repo root:  sbatch --array=0-20 experiments/offline.sh
# Then:  python -m analysis.stats measure "runs/offline_<id>/*/rows.jsonl" --ref "honest/text/load0"
#SBATCH --job-name=lf-offline
#SBATCH --time=10:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%A_%a.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
CHANNELS=(none text artifact session latent kv stream)
SEED=$((TASK_ID / 7))
CH=${CHANNELS[$((TASK_ID % 7))]}
python -m benchmark.measure --n 200 --seed "$SEED" --channel "$CH" --transplant \
    --out "runs/offline_${JOB_ID}/seed${SEED}_${CH}"
