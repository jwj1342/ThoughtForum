#!/bin/bash
# E0s4: SecretBench with saboteurs. Every agent's message misstates its method's format (claims stay
# honest). Text readers get the lie; a trusted writer head reads the author's whole context, so does
# its latent carry what the author knows or what it says? Compare with E0s3 (honest authors).
#   sbatch experiments/e0s4.sh                      (the untrained gist head, i.e. the method)
#   sbatch --export=ALL,HEAD=runs/<dir>/writer_head.pt experiments/e0s4.sh   (a trained head)
#SBATCH --job-name=lf-e0s4
#SBATCH --time=04:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
OUT="runs/e0s4_${JOB_ID}"
HEAD="${HEAD:-random:16}"   # default: the untrained gist writer (16 random vocabulary queries, identity map)
COMMON=(--backend hf --tasks secret:40 --n-agents 3 --rounds 8 --spec private --memory true --probe false
        --overclaim-frac 1.0 --overclaim-mode mislead)
python -m forum.run "${COMMON[@]}" --channel latent --writer-head "$HEAD" --save-latents true --out "$OUT/latent"
python -m forum.run "${COMMON[@]}" --channel text --out "$OUT/text"
