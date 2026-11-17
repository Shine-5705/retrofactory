#!/usr/bin/env bash
# Create the four RetroFactory seats as Band Desktop-owned OpenCode agents.
# Run once after `band init` succeeded and `band preflight` shows the account as ok.
# Usage: factory/create_seats.sh /absolute/path/to/result-repo
set -euo pipefail
REPO="${1:?absolute path of the result repository}"
KIT="$(cd "$(dirname "$0")/.." && pwd)"
declare -A MODEL=(
  [coordinator]=opencode/glm-5.3-flash-free
  [implementer]=opencode/deepseek-v4.1-flash-free
  [reviewer]=opencode/big-pickle
  [retro]=opencode/mimo-v2.6-flash-free
)
for seat in coordinator implementer reviewer retro; do
  band agent create --session "rf-$seat" --name "$seat" \
    --description "RetroFactory $seat seat" \
    --cwd "$REPO" --transport opencode \
    --runtime-model "${MODEL[$seat]}" \
    --instructions-file "$KIT/mandates/$seat.md"
done
band list
