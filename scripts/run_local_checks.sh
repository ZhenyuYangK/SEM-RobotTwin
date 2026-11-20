#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1

echo '== 1/4 Verify input hashes and run unit tests =='
sha256sum -c reports/teacher_inputs_sha256.txt
python3 -m unittest discover -s tests -v

echo '== 2/4 Source URDF static structural audit =='
python3 scripts/audit_urdf.py --urdf teacher_inputs/arx5_description_isaac.urdf \
  --robotwin src/RoboTwin --output reports/urdf_audit.json

echo '== 3/4 Locked source checkout audit =='
python3 scripts/audit_sources.py --workspace . >/dev/null
if python3 - <<'PY_SOURCE'
import json
from pathlib import Path

report = json.loads(Path('reports/source_revisions.json').read_text(encoding='utf-8'))
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
