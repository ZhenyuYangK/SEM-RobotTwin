#!/usr/bin/env bash
# Only clone public source code when explicitly requested; never download pretrained weights/assets.
set -euo pipefail
if [[ "${1:-}" != "--clone" ]]; then
  echo 'Only explicit --clone is supported. Usage: bash scripts/bootstrap_sources.sh --clone' >&2
  exit 2
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/src" "$ROOT/reports"
command -v git >/dev/null || { echo 'git is required' >&2; exit 2; }
function clone_or_report() {
  local url="$1" path="$2"
  if [[ -e "$path" ]]; then
    if [[ ! -d "$path/.git" ]]; then echo "Conflict: $path already exists but is not a Git checkout" >&2; return 1; fi
    echo "EXISTS (not modified): $path"
  else
    git clone --filter=blob:none "$url" "$path"
  fi
}
clone_or_report 'https://github.com/HorizonRobotics/RoboOrchardLab.git' "$ROOT/src/RoboOrchardLab"
clone_or_report 'https://github.com/RoboTwin-Platform/RoboTwin.git' "$ROOT/src/RoboTwin"
PIN=e71140e9734e69686daa420a9be8b75a20ff4587
CURRENT="$(git -C "$ROOT/src/RoboTwin" rev-parse HEAD)"
if [[ "$CURRENT" != "$PIN" ]]; then
  [[ -z "$(git -C "$ROOT/src/RoboTwin" status --porcelain)" ]] || { echo 'RoboTwin has local changes: refusing checkout' >&2; exit 1; }
  git -C "$ROOT/src/RoboTwin" checkout --detach "$PIN"
fi
python3 "$ROOT/scripts/audit_sources.py" --workspace "$ROOT"
echo 'Source cloned/pinned; next check compatibility before any installation.'
