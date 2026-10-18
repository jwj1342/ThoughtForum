#!/bin/bash
# E0d: coherent lies. One agent in three is told to claim DONE and hide failures in every report, so a
# lie leaves no trace in its own text (unlike E0's harness rewrite of the STATUS line). All 77 projects.
#   0: latent channel: does the writer-context latent still carry the real test result? (neutral control)
#   1: text channel, deceive: do coherent lies mislead peers more than crude ones?
#   2: text channel, crude rewrite (always), same projects, as the comparison for 1
# Run from the repo root:  sbatch --array=0-2 experiments/e0d.sh
#SBATCH --job-name=lf-e0d
#SBATCH --time=03:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%A_%a.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh

OUT="runs/e0d_${JOB_ID}/task${TASK_ID}"
COMMON=(--backend hf --tasks classeval:all --n-agents 3 --rounds 8 --overclaim-frac 0.34
        --grid trust=blind,attested --out "$OUT")
case "${TASK_ID}" in
  0) python -m forum.run "${COMMON[@]}" --channel latent --overclaim-mode deceive --save-latents true
     python -m analysis.neutral_probe "$OUT"/*/latents.pt --out "$OUT/neutral_probe.json" ;;
  1) python -m forum.run "${COMMON[@]}" --channel text --overclaim-mode deceive ;;
  2) python -m forum.run "${COMMON[@]}" --channel text --overclaim-mode always ;;
esac
