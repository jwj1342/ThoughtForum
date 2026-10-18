#!/bin/bash
# Smoke test for the HF backend: 3 projects x 4 conditions on one MIG slice.
# Submit from code/:  sbatch jobs/smoke.sbatch
#SBATCH --job-name=lf-smoke
#SBATCH --account=def-zhouyang
#SBATCH --time=01:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "$SLURM_SUBMIT_DIR"
source setup_env.sh
nvidia-smi --query-gpu=name,memory.total --format=csv

python -m forum.run --backend hf --tasks classeval:0-2 --n-agents 3 --rounds 6 \
    --overclaim-frac 0.34 \
    --grid channel=text,latent --grid trust=blind,attested \
    --save-latents true --out "runs/smoke_${SLURM_JOB_ID}"
