#!/bin/bash
# E0s2: SecretBench follow-up (final code is now saved in projects.jsonl).
#   text, private spec: how much of the loss is reading (R11; the original run also had a deps_wait
#   option, which never triggered and has been removed);
#   latent through the E1w fold-0 writer head (trained on ClassEval only): does a trained writer
#   carry a secret it was never trained on? Latents are saved for SecretBench-specific E1w.
# Run from the repo root:  sbatch experiments/e0s2.sh
#SBATCH --job-name=lf-e0s2
#SBATCH --time=02:30:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh

OUT="runs/e0s2_${JOB_ID}"
COMMON=(--backend hf --tasks secret:40 --n-agents 3 --rounds 8 --spec private)
python -m forum.run "${COMMON[@]}" --channel text --out "$OUT/text"
python -m forum.run "${COMMON[@]}" --channel latent --writer-head runs/e1w_24437567/writer_head.pt \
  --save-latents true --out "$OUT/latent_wh"
