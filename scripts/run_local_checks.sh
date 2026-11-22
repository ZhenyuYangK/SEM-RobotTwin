#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1
report_dir="$(mktemp -d)"
trap 'rm -f -- "$report_dir/urdf_audit.json" "$report_dir/source_revisions.json"; rmdir -- "$report_dir"' EXIT

echo '== 1/4 Verify available local input hashes and run unit tests =='
while read -r checksum input; do
  if [[ -f "$input" ]]; then
    printf '%s  %s\n' "$checksum" "$input" | sha256sum -c -
  else
    printf 'Skip checksum for absent local input: %s\n' "$input"
  fi
done < reports/teacher_inputs_sha256.txt
python3 -m unittest discover -s tests -v

echo '== 2/4 Source URDF static structural audit =='
urdf=teacher_inputs/arx5_description_isaac.urdf
if [[ -f "$urdf" ]]; then
  python3 scripts/audit_urdf.py --urdf "$urdf" \
    --robotwin src/RoboTwin --output "$report_dir/urdf_audit.json"
else
  echo 'URDF audit skipped. See docs/CLOUD_HANDOFF.md for the pinned RoboTwin asset.'
fi

echo '== 3/4 Locked source checkout audit =='
python3 scripts/audit_sources.py --workspace . --output "$report_dir/source_revisions.json" >/dev/null
if python3 - "$report_dir/source_revisions.json" <<'PY_SOURCE'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for issue in report['not_ready']:
    print(' -', issue)
raise SystemExit(bool(report['not_ready']))
PY_SOURCE
then
  echo '== 4/4 Selected task validation =='
  if ! python3 scripts/discover_tasks.py --workspace . --validate; then
    echo 'Task configuration needs review. Offline tests completed.' >&2
    exit 1
  fi
else
  echo 'Source check NOT_READY. Selected task validation skipped.'
fi
