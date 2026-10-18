#!/bin/bash
# E0s: SecretBench (benchmark/secretbench.py), where consumers can only learn a private record
# format through the forum. Honest team, blind trust, 40 projects x 4 methods (120 consumers).
# Short conditions, so they are bundled in one job.  Run from the repo root:  sbatch experiments/e0s.sh
#SBATCH --job-name=lf-e0s
#SBATCH --time=02:30:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh

OUT="runs/e0s_${JOB_ID}"
COMMON=(--backend hf --tasks secret:40 --n-agents 3 --rounds 8)
python -m forum.run "${COMMON[@]}" --spec private --grid channel=none,text,latent --save-latents true --out "$OUT/private"
python -m forum.run "${COMMON[@]}" --spec full --channel none --out "$OUT/full"
