#!/bin/bash
# E1a: train the read-in adapter on E0 latents.  Run from the repo root:
#   sbatch --export=ALL,LATENTS='runs/e0_<id>/task1/*/latents.pt runs/e0_<id>/task2/*/latents.pt' experiments/e1a.sh
# Quick functional test:  sbatch --time=00:30:00 --export=ALL,LATENTS='runs/smoke_*/*/latents.pt',EXTRA='--steps 30 --eval-rows 12' experiments/e1a.sh
#SBATCH --job-name=lf-e1a
#SBATCH --time=03:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
python -m training.reader --latents $LATENTS --out "runs/e1a_${JOB_ID}" $EXTRA
