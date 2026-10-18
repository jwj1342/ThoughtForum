#!/bin/bash
# E0s3: SecretBench forum with agent memory (an agent sees its own earlier code for a dependency),
# the explicit "read my code" baseline, and a writer head (default: the untrained gist head) with shuffle.
#   sbatch jobs/e0s3.sbatch                      (the untrained gist head, i.e. the method)
#   sbatch --export=ALL,HEAD=runs/<dir>/writer_head.pt jobs/e0s3.sbatch   (a trained head)
#SBATCH --job-name=lf-e0s3
#SBATCH --account=def-zhouyang
#SBATCH --time=05:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "$SLURM_SUBMIT_DIR"
source setup_env.sh
OUT="runs/e0s3_${SLURM_JOB_ID}"
HEAD="${HEAD:-random:16}"   # default: the untrained gist writer (16 random vocabulary queries, identity map)
COMMON=(--backend hf --tasks secret:40 --n-agents 3 --rounds 8 --spec private --memory true --probe false)
python -m forum.run "${COMMON[@]}" --channel latent --writer-head "$HEAD" --save-latents true \
    --grid control=none,shuffle --out "$OUT/latent"
python -m forum.run "${COMMON[@]}" --channel text --grid source=report,artifact --out "$OUT/text"
python -m forum.run "${COMMON[@]}" --channel none --out "$OUT/none"
