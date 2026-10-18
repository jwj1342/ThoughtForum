#!/bin/bash
# E1b: rerun the latent forum with a trained read-in adapter (E1a), same 30 projects as E0.
#   sbatch --export=ALL,ADAPTER=runs/e1a_<id>/adapter.pt,SOURCE=report jobs/e1b.sbatch
#SBATCH --job-name=lf-e1b
#SBATCH --account=def-zhouyang
#SBATCH --time=04:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "$SLURM_SUBMIT_DIR"
source setup_env.sh
python -m forum.run --backend hf --tasks classeval:0-29 --n-agents 3 --rounds 8 --overclaim-frac 0.34 \
    --channel latent --source "${SOURCE:-report}" --reader-adapter "$ADAPTER" \
    --grid trust=blind,attested --grid control=none,shuffle --save-latents true --out "runs/e1b_${SLURM_JOB_ID}"
