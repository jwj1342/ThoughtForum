#!/bin/bash
# Offline SecretBench measurement (benchmark/measure.py), the main measurement: 40 projects per condition.
#   task 0: honest reports, plus the no-message floor     task 1: omitted format (what leaks)
#   task 2: false format (follows what the author knows or what it says)
#   task 3: capacity: honest, tags of 2 / 8 / 16 letters (about 14 / 43 / 80 bits; 4 letters is about 23)
# Channels: text, the latent post, both; writers: the method (random:16) and the pooling baseline (chunk:16).
# Run from the repo root:  sbatch --array=0-3 experiments/measure.sh   or   TASK=2 bash experiments/measure.sh
#SBATCH --job-name=lf-measure
#SBATCH --time=04:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%A_%a.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source experiments/env.sh
OUT="runs/measure_${JOB_ID}"
M=(python -m benchmark.measure --n 40 --writer random:16,chunk:16)
case "$TASK_ID" in
  0) "${M[@]}" --speech honest --channel none,text,latent,both --out "$OUT/honest" ;;
  1) "${M[@]}" --speech omit --channel text,latent,both --out "$OUT/omit" ;;
  2) "${M[@]}" --speech lie --channel text,latent,both --out "$OUT/lie" ;;
  3) for L in 2 8 16; do
       python -m benchmark.measure --n 40 --writer random:16 --speech honest --channel text,latent \
           --tag-len "$L" --out "$OUT/capacity_$L"
     done ;;
esac
