#!/bin/bash
# Smoke test on a real model (< 1 h on one GPU): every entry point runs once, briefly.
#   unit tests (including the tiny in-memory HF model) -> the method and the text baseline in a
#   2-project SecretBench forum -> the offline SecretBench evaluation and 2 training steps of each
#   ablation -> the linear probes on the saved posts.
# Run from the repo root:  sbatch experiments/smoke.sh   or   bash experiments/smoke.sh
#SBATCH --job-name=lf-smoke
#SBATCH --time=01:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
OUT="runs/smoke_${JOB_ID}"

python -m unittest discover -s tests -t .
python -m forum.run --backend hf --tasks secret:2 --spec private --memory true --rounds 3 --probe false \
    --channel latent --writer-head random:16 --save-latents true --out "$OUT/forum"
python -m forum.run --backend hf --tasks secret:2 --spec private --memory true --rounds 3 --channel text --out "$OUT/forum"
DUMP="$OUT/forum/*/latents.pt"
python -m training.secret --test-latents "$DUMP" --n-train 4 --steps 2 --batch 1 --eval-rows 1 --out "$OUT/secret"
python -m training.reader --latents "$DUMP" --steps 2 --batch 2 --eval-rows 2 --holdout 0.5 --out "$OUT/reader"
python -m training.writer --latents "$DUMP" --steps 2 --batch 1 --eval-rows 2 --holdout 0.5 --out "$OUT/writer"
python -m analysis.linprobe $DUMP > /dev/null
python -m analysis.secret_cross "$OUT"/forum/*/
echo "smoke test passed: $OUT"
