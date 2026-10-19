#!/bin/bash
# Smoke test on a real model (< 1 h on one GPU): every entry point runs once, briefly.
#   unit tests (including the tiny in-memory HF model) -> the offline measurement on 3 projects, every
#   channel, and with 3 posts per reader -> the forum on 2 projects with each kind of post -> 2 training
#   steps of each ablation and the linear probes on the saved latent posts -> the statistics.
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
python -m benchmark.measure --n 3 --transplant --out "$OUT/offline"
python -m benchmark.measure --n 4 --load 3 --speech lie --channel text,session,kv,stream --out "$OUT/offline_load"
F=(python -m forum.run --backend hf --tasks secret:2 --spec private --memory true --rounds 3 --probe false)
"${F[@]}" --channel latent --writer-head random:16 --save-latents true --out "$OUT/forum"
"${F[@]}" --channel text --grid source=report,session --out "$OUT/forum"
"${F[@]}" --channel stream --out "$OUT/forum"
DUMP="$OUT/forum/*/latents.pt"
python -m training.reader --latents "$DUMP" --steps 2 --batch 2 --eval-rows 2 --holdout 0.5 --out "$OUT/reader"
python -m training.writer --latents "$DUMP" --steps 2 --batch 1 --eval-rows 2 --holdout 0.5 --out "$OUT/writer"
python -m analysis.linprobe $DUMP > /dev/null
python -m analysis.stats measure "$OUT/offline/rows.jsonl" --ref "honest/text/load0"
python -m analysis.stats forum "$OUT"/forum/*/
echo "smoke test passed: $OUT"
