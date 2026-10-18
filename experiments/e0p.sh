#!/bin/bash
# E0p: make communication necessary. Under spec=private an agent sees only the docstring of its own
# method; callers must learn the interfaces of the methods they call from the forum. Honest team,
# blind trust, all 70 projects (86 dependent methods). Read dep_pass_iso.
#   0: private, none vs text    1: private, latent (training-free)    2: full spec, none (the oracle)
# Run from the repo root:  sbatch --array=0-2 experiments/e0p.sh
#SBATCH --job-name=lf-e0p
#SBATCH --time=03:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%A_%a.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh

COMMON=(--backend hf --tasks classeval:all --n-agents 3 --rounds 8 --out "runs/e0p_${JOB_ID}/task${TASK_ID}")
case "${TASK_ID}" in
  0) python -m forum.run "${COMMON[@]}" --spec private --grid channel=none,text ;;
  1) python -m forum.run "${COMMON[@]}" --spec private --channel latent --save-latents true ;;
  2) python -m forum.run "${COMMON[@]}" --spec full --channel none ;;
esac
