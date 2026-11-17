#!/usr/bin/env bash
# Create the four RetroFactory seats as Band Desktop-owned OpenCode agents.
# Run once after `band init` succeeded and `band preflight` shows the account as ok.
# Usage: factory/create_seats.sh /absolute/path/to/run-folder
# The run folder is the seats' working directory and holds ONLY the result repository.
# Keep task files, held specifications, credentials and earlier runs outside it.
set -euo pipefail
RUN="${1:?absolute path of the per-run folder that holds only the result repository}"
KIT="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="${ACP_QUIET_LOG_DIR:-$KIT/../ops/acp-quiet}"
# Primary model first, then fallbacks. Must match each mandate's Model: line.
declare -A MODELS=(
  [coordinator]=opencode/glm-5.3-flash-free,opencode/longcat-2.5-free,opencode/hy4-flash-free
  [implementer]=opencode/deepseek-v4.1-flash-free,opencode/big-pickle,opencode/longcat-2.5-free
  [reviewer]=opencode/big-pickle,opencode/deepseek-v4.1-flash-free,opencode/glm-5.3-flash-free
  [retro]=opencode/mimo-v2.6-flash-free,opencode/hy4-flash-free,opencode/nemotron-3.5-lightning-free
)
for seat in coordinator implementer reviewer retro; do
  primary="${MODELS[$seat]%%,*}"
  band agent create --session "rf-$seat" --name "$seat" \
    --description "RetroFactory $seat seat" \
    --cwd "$RUN" --transport opencode \
    --runtime-model "$primary" \
    --instructions-file "$KIT/mandates/$seat.md"
  # Launch OpenCode through acp-quiet: drops bare acknowledgement replies and fails over
  # to the next model on a usage-limit or upstream error (see factory/acp-quiet.py).
  band runtime template set --session "rf-$seat" --spawn-cwd "$RUN" \
    --spawn-command "$(command -v python3)" \
    --spawn-arg="$KIT/factory/acp-quiet.py" --spawn-arg=--seat --spawn-arg="$seat" \
    --spawn-arg=--models --spawn-arg="${MODELS[$seat]}" --spawn-arg=--log-dir --spawn-arg="$LOGDIR" \
    --spawn-arg=-- --spawn-arg=opencode --spawn-arg=acp
  # The thread model is what new room sessions actually launch with; set it explicitly.
  band runtime settings --session "rf-$seat" --model "$primary"
done
band list
# For each later run, re-point the seats instead of re-creating them:
#   band runtime template set --as <owner>/<seat> --spawn-cwd <new run folder>
# (the wrapper arguments are preserved), then settle and detach finished rooms
# (see RUNBOOK 0d) before starting the new room.
