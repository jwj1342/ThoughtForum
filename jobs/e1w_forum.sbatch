#!/bin/bash
# E1w in the forum: private spec, latent channel written by a trained head, on the projects that head
# never saw (cross-fitting). Shuffle control included: if the head's latents carry content, shuffling
# them should hurt.  Submit from code/, usually as a dependency of the E1w job:
#   sbatch --dependency=afterok:<e1w job> --export=ALL,HEAD_DIR=runs/e1w_<id> jobs/e1w_forum.sbatch
#SBATCH --job-name=lf-e1wf
#SBATCH --account=def-zhouyang
#SBATCH --time=03:00:00
#SBATCH --gpus=h100_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "$SLURM_SUBMIT_DIR"
source ./setup_env.sh
python -m forum.run --backend hf --tasks "classeval:@$HEAD_DIR/test_projects.json" --n-agents 3 --rounds 8 \
  --spec private --channel latent --writer-head "$HEAD_DIR/writer_head.pt" --grid control=none,shuffle \
  --out "$HEAD_DIR/forum"
