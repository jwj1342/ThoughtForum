#!/bin/bash
# H4 control: probe writer-context latents vs neutral re-encodings of the same text.
#   sbatch --export=ALL,LATENTS='runs/e0_<id>/task1/*/latents.pt',OUT=runs/e0_<id>/neutral_probe.json experiments/neutral.sh
#SBATCH --job-name=lf-neutral
#SBATCH --time=00:45:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
python -m analysis.neutral_probe $LATENTS --out "$OUT"
