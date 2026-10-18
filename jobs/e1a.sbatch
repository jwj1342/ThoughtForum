#!/bin/bash
# E1a: train the read-in adapter on E0 latents.  Submit from code/:
#   sbatch --export=ALL,LATENTS='runs/e0_<id>/task1/*/latents.pt runs/e0_<id>/task2/*/latents.pt' jobs/e1a.sbatch
# Quick functional test:  sbatch --time=00:30:00 --export=ALL,LATENTS='runs/smoke_*/*/latents.pt',EXTRA='--steps 30 --eval-rows 12' jobs/e1a.sbatch
#SBATCH --job-name=lf-e1a
#SBATCH --account=def-zhouyang
#SBATCH --time=03:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "$SLURM_SUBMIT_DIR"
source setup_env.sh
python -m model.train_reader --latents $LATENTS --out "runs/e1a_${SLURM_JOB_ID}" $EXTRA
