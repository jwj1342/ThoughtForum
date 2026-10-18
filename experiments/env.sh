# Sourced by every experiment script, from the repo root. Works anywhere:
#   locally:      activate your environment (pip install -r requirements.txt), then  bash experiments/<name>.sh
#   with Slurm:   sbatch --account=<your account> experiments/<name>.sh
# Personal settings (model path, ...) go in experiments/local.sh, which git ignores, e.g.
#   export LF_MODEL=/path/to/Qwen3-8B
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-${OMP_NUM_THREADS:-4}}"
# Output names: the Slurm job id, or a timestamp when run locally; array scripts take TASK_ID (or $TASK).
JOB_ID="${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-local$(date +%m%d%H%M%S)}}"
TASK_ID="${SLURM_ARRAY_TASK_ID:-${TASK:-0}}"
mkdir -p runs
[ -f experiments/local.sh ] && source experiments/local.sh
# Alliance (Compute Canada) clusters set CC_CLUSTER: there, use modules and the wheelhouse instead.
[ -n "$CC_CLUSTER" ] && source experiments/alliance.sh
true
