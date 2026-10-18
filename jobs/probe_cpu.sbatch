#!/bin/bash
# Linear probes on saved latents, CPU only (no model needed).  Submit from code/:
#   sbatch --export=ALL,LATENTS='runs/e0_<id>/task1/*/latents.pt' jobs/probe_cpu.sbatch
#SBATCH --job-name=lf-probe
#SBATCH --account=def-zhouyang
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "$SLURM_SUBMIT_DIR"
export LF_MODEL_SRC=/nonexistent   # skip copying the weights
source setup_env.sh
python -m analysis.linprobe $LATENTS $EXTRA
