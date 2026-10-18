#!/bin/bash
# E0c and E0k on the first 30 projects (as E0). Grid values contain commas, so they live here rather
# than in --export (which splits on commas).  Run from the repo root:  sbatch --array=0-1 experiments/e0ck.sh
#   0 (E0c): text, completion pressure; honest vs 1/3 pressured x attested vs crosscheck (peer-written tests)
#   1 (E0k): latent without pooling (k=128), 1/3 falsified, blind vs attested; saves latents (with contexts)
#SBATCH --job-name=lf-e0ck
#SBATCH --time=03:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%A_%a.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh

COMMON=(--backend hf --tasks classeval:0-29 --n-agents 3 --rounds 8)
case "${TASK_ID}" in
  0) OUT="runs/e0c_${JOB_ID}"
     python -m forum.run "${COMMON[@]}" --out "$OUT" --channel text --overclaim-mode pressure \
       --grid overclaim_frac=0,0.34 --grid trust=attested,crosscheck ;;
  1) OUT="runs/e0k_${JOB_ID}"
     python -m forum.run "${COMMON[@]}" --out "$OUT" --channel latent --latent-k 128 --overclaim-frac 0.34 \
       --grid trust=blind,attested --save-latents true
     python -m analysis.linprobe "$OUT"/*/latents.pt > /dev/null ;;
esac
