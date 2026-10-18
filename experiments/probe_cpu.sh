#!/bin/bash
# Linear probes on saved latents, CPU only (no model needed).  Run from the repo root:
#   sbatch --export=ALL,LATENTS='runs/e0_<id>/task1/*/latents.pt' experiments/probe_cpu.sh
#SBATCH --job-name=lf-probe
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --output=runs/slurm-%x-%j.out

set -eo pipefail  # no -u: Lmod reads unset variables
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
unset LF_MODEL_SRC   # no model needed: skip copying the weights
source experiments/env.sh
python -m analysis.linprobe $LATENTS $EXTRA
