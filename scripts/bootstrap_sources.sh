#!/usr/bin/env bash
# Fetch source metadata first and materialize text source files only.
set -euo pipefail
if [[ "$#" != 1 || "$1" != "--clone" ]]; then
  echo 'Usage: bash scripts/bootstrap_sources.sh --clone' >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
read -r PIN SEM_PIN < <(
  cd "$ROOT/scripts"
  python3 -B -c 'from audit_sources import PIN, SEM_PIN; print(PIN, SEM_PIN)'
)
export GIT_LFS_SKIP_SMUDGE=1 GIT_TERMINAL_PROMPT=0
mkdir -p "$ROOT/src" "$ROOT/reports"

clone_source() {
  local url="$1" path="$2" revision="${3:-}"
  if [[ ! -e "$path" ]]; then
    git -c submodule.recurse=false clone --depth=1 --filter=blob:none --no-checkout --no-recurse-submodules "$url" "$path"
  elif [[ ! -d "$path/.git" ]]; then
    echo "Conflict: $path is not a Git checkout" >&2
    return 1
  fi

  local current
  current="$(git -C "$path" rev-parse HEAD)"
  if [[ -z "$(git -C "$path" ls-files)" ]]; then
    if [[ -n "$revision" && "$current" != "$revision" ]]; then
      git -C "$path" -c submodule.recurse=false fetch --no-tags --depth=1 --filter=blob:none origin "$revision"
    fi
    git -C "$path" sparse-checkout set --no-cone --stdin <<'PATTERNS'
*.py
*.sh
*.yml
*.yaml
*.json
*.toml
*.ini
*.cfg
*.md
*.rst
.gitattributes
.gitignore
.gitmodules
/LICENSE*
/requirements*.txt
!**/assets/
!**/data/
!**/datasets/
!**/weights/
!**/checkpoints/
PATTERNS
    git -C "$path" -c submodule.recurse=false checkout --detach "${revision:-$current}"
  elif [[ -n "$revision" && "$current" != "$revision" ]]; then
    echo "Existing checkout at $current has been preserved. Expected $revision at $path." >&2
    return 1
  fi
  git -C "$path" rev-parse HEAD
}

clone_source 'https://github.com/HorizonRobotics/RoboOrchardLab.git' "$ROOT/src/RoboOrchardLab" "$SEM_PIN"
clone_source 'https://github.com/RoboTwin-Platform/RoboTwin.git' "$ROOT/src/RoboTwin" "$PIN"
