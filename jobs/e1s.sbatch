#!/bin/bash
# E1s: train the writer head so a frozen reader can use a SecretBench producer's latent post.
# Submit from code/:
#   sbatch --export=ALL,TEST='runs/e0s_<id>/private/latent-*/latents.pt' jobs/e1s.sbatch
# A 2-step smoke run goes first, so a bug fails within minutes instead of after training.
#SBATCH --job-name=lf-e1s
#SBATCH --account=def-zhouyang
#SBATCH --time=04:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "$SLURM_SUBMIT_DIR"
source setup_env.sh
OUT="runs/e1s_${SLURM_JOB_ID}"
python -m model.train_secret --test-latents $TEST --out "$OUT/smoke" --n-train 8 --steps 2 --eval-rows 2 $EXTRA
python -m model.train_secret --test-latents $TEST --out "$OUT" $EXTRA
