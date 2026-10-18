#!/bin/bash
# E0, the first real comparison, on 30 projects with 3 agents each:
#   none / text / latent channels; content controls (shuffle, zero) on latent; report vs artifact source;
#   blind vs attested trust; one third of agents falsify DONE (task 3: natural overclaiming under pressure).
# Only one channel per array task, so each task needs < 12h. Submit from code/:
#   sbatch --array=0-3 jobs/e0.sbatch
#SBATCH --job-name=lf-e0
#SBATCH --account=def-zhouyang
#SBATCH --time=06:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%A_%a.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "$SLURM_SUBMIT_DIR"
source setup_env.sh

COMMON=(--backend hf --tasks classeval:0-29 --n-agents 3 --rounds 8 --overclaim-frac 0.34
        --grid trust=blind,attested --save-latents true --out "runs/e0_${SLURM_ARRAY_JOB_ID}/task${SLURM_ARRAY_TASK_ID}")
case "$SLURM_ARRAY_TASK_ID" in
  0) python -m forum.run "${COMMON[@]}" --grid channel=none,text ;;
  1) python -m forum.run "${COMMON[@]}" --channel latent --grid control=none,shuffle,zero ;;
  2) python -m forum.run "${COMMON[@]}" --channel latent --source artifact --grid control=none,shuffle ;;
  # natural (not injected) overclaiming: honest team vs one agent under completion pressure
  3) python -m forum.run "${COMMON[@]}" --channel text --overclaim-mode pressure --grid overclaim_frac=0,0.34 ;;
esac

# Linear probes on the saved latent posts (seconds on CPU)
for f in runs/e0_${SLURM_ARRAY_JOB_ID}/task${SLURM_ARRAY_TASK_ID}/*/latents.pt; do
  [ -e "$f" ] || continue
  python -m analysis.linprobe "$f" > /dev/null
done
