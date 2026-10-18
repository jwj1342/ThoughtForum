#!/bin/bash
# Generic run: sbatch --export=ALL,NAME=x,ARGS="--channel text" experiments/run.sh
# --export splits on commas, so ARGS must not contain any (no --grid k=a,b here; use a dedicated script).
#SBATCH --job-name=lf-run
#SBATCH --time=03:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
OUT="runs/${NAME:-run}_${JOB_ID}"
python -m forum.run --backend hf --tasks classeval:0-29 --n-agents 3 --rounds 8 $ARGS --out "$OUT"
for f in "$OUT"/*/latents.pt; do
  [ -e "$f" ] || continue
  python -m analysis.linprobe "$f" > /dev/null
done
