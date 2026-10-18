#!/bin/bash
# Usage: source setup_env.sh
# On a login node this only loads Python, which is enough for the mock backend and tests.
# Inside a Slurm job it also builds the venv in $SLURM_TMPDIR from the Alliance wheelhouse.
module purge
module load StdEnv/2023 python/3.11.5

LF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$LF_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_XET=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"

# Weights are read once, sequentially, onto node-local disk. Loading them lazily over
# /scratch via mmap page faults was ~3 MB/s when several jobs ran at once.
LF_MODEL_SRC="${LF_MODEL_SRC:-/scratch/jwj/models/Qwen3-8B}"
if [ -n "$SLURM_TMPDIR" ] && [ -d "$LF_MODEL_SRC" ]; then
    LF_MODEL="$SLURM_TMPDIR/$(basename "$LF_MODEL_SRC")"
    [ -d "$LF_MODEL" ] || cp -r "$LF_MODEL_SRC" "$SLURM_TMPDIR/"
    export LF_MODEL
fi

if [ -n "$SLURM_TMPDIR" ]; then
    if [ ! -d "$SLURM_TMPDIR/lf_env" ]; then
        virtualenv --no-download -q "$SLURM_TMPDIR/lf_env"
        source "$SLURM_TMPDIR/lf_env/bin/activate"
        pip install --no-index -q --upgrade pip
        pip install --no-index -q -r "$LF_ROOT/requirements.txt"
    else
        source "$SLURM_TMPDIR/lf_env/bin/activate"
    fi
fi
