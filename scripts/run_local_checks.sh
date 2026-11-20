#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo '== 1/3 Python offline unit tests =='
python3 -m unittest discover -s tests -v
echo '== 2/3 Teacher URDF static structural audit =='
python3 scripts/audit_urdf.py --urdf teacher_inputs/arx5_description_isaac.urdf --output reports/urdf_audit.json
echo '== 3/3 Source availability (NOT a blocker for offline tests) =='
python3 scripts/audit_sources.py --workspace "$ROOT" --output reports/source_revisions.json >/dev/null
python3 - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('reports/source_revisions.json').read_text(encoding='utf-8'))
if r['not_ready']:
    print('Source check NOT_READY (normal before explicit git clone):')
    for issue in r['not_ready']: print(' -', issue)
else:
    print('Source paths present; manual API compatibility review still required')
print('Local offline checks complete; this does NOT validate GPU training/simulation.')
PY
