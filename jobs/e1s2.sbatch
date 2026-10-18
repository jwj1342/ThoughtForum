#!/bin/bash
# E1s2: why did E1s training erase the content that the untrained head carried? Three heads, one job:
#   step0  - the untrained head (random vocabulary queries, identity map): self vs other latent
#   qonly  - train only the queries, lr 1e-4
#   lowlr  - full head, lr 5e-5, no recon objective
# Each trained head is tracked every 150 steps on 20 real and 20 synthetic held-out posts.
#   sbatch --export=ALL,TEST='runs/e0s_<id>/private/latent-*/latents.pt' jobs/e1s2.sbatch
#SBATCH --job-name=lf-e1s2
#SBATCH --account=def-zhouyang
#SBATCH --time=03:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "$SLURM_SUBMIT_DIR"
source setup_env.sh
OUT="runs/e1s2_${SLURM_JOB_ID}"
T=(--test-latents $TEST --skip-baselines)
python -m model.train_secret "${T[@]}" --steps 0 --out "$OUT/step0"
python -m model.train_secret "${T[@]}" --q-only --lr 1e-4 --steps 600 --eval-every 150 --out "$OUT/qonly"
python -m model.train_secret "${T[@]}" --lr 5e-5 --tasks secret,use --steps 600 --eval-every 150 --out "$OUT/lowlr"
