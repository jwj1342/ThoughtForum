#!/bin/bash
# E1w: train the protocol's writer head; peers' readers stay frozen.  Submit from code/:
#   sbatch --export=ALL,LATENTS='runs/e0p_<id>/task1/*/latents.pt',EXTRA='--steps 1500' jobs/e1w.sbatch
# Needs dumps written with --save-latents true after 2026-10-18 (rows carry the writer's context).
#SBATCH --job-name=lf-e1w
#SBATCH --account=def-zhouyang
#SBATCH --time=03:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "$SLURM_SUBMIT_DIR"
source setup_env.sh
python -m model.train_writer --latents $LATENTS --out "runs/e1w_${SLURM_JOB_ID}" $EXTRA
