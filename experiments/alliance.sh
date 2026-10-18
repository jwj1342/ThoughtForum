# Only for Alliance (Compute Canada) clusters; sourced by env.sh when CC_CLUSTER is set.
# Loads Python from the module system. Inside a job it also builds the venv on node-local disk
# from the Alliance wheelhouse and copies the model weights there (LF_MODEL_SRC): several jobs
# reading weights lazily from the shared filesystem at once were as slow as ~3 MB/s.
module purge
module load StdEnv/2023 python/3.11.5
if [ -n "$SLURM_TMPDIR" ]; then
    export TMPDIR="$SLURM_TMPDIR" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # compute nodes have no internet
    if [ ! -d "$SLURM_TMPDIR/lf_env" ]; then
        virtualenv --no-download -q "$SLURM_TMPDIR/lf_env"
        source "$SLURM_TMPDIR/lf_env/bin/activate"
        pip install --no-index -q --upgrade pip
        # the versions all results so far were run with, from the wheelhouse
        pip install --no-index -q -r requirements.txt torch==2.9.1 transformers==4.57.6 numpy==2.2.2
    else
        source "$SLURM_TMPDIR/lf_env/bin/activate"
    fi
    if [ -n "$LF_MODEL_SRC" ] && [ -d "$LF_MODEL_SRC" ]; then
        export LF_MODEL="$SLURM_TMPDIR/$(basename "$LF_MODEL_SRC")"
        [ -d "$LF_MODEL" ] || cp -r "$LF_MODEL_SRC" "$SLURM_TMPDIR/"
    fi
fi
