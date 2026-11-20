#!/usr/bin/env python3
"""Read-only path/git/selected config audit for pinned SEM and RoboTwin source trees."""
import argparse
import ast
import json
import re
import subprocess
from pathlib import Path

PIN = 'e71140e9734e69686daa420a9be8b75a20ff4587'
REQUIRED = {
    'RoboOrchardLab': [
        'projects/sem/robotwin/README.md',
        'projects/sem/robotwin/config_sem_robotwin.py',
        'projects/sem/robotwin/train.py',
        'projects/sem/robotwin/sem_policy/deploy_policy.py',
        'projects/sem/robotwin/sem_policy/deploy_policy.yml',
        'robo_orchard_lab/dataset/robotwin/robotwin_packer.py',
    ],
    'RoboTwin': ['collect_data.sh', 'script/eval_policy.py', 'envs', 'policy', 'task_config'],
}


def git_rev(root):
    if not (root / '.git').exists():
        return None
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def config_constants(file):
    if not file.is_file():
        return {}
    t = ast.parse(file.read_text(encoding='utf-8'))
    vals = {}
    for node in t.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'config'):
            continue
        if not isinstance(node.value, ast.Call) or not isinstance(node.value.func, ast.Name) or node.value.func.id != 'dict':
            continue
        for kw in node.value.keywords:
            if kw.arg not in {'batch_size', 'max_step', 'multi_task', 'task_names', 'with_depth', 'with_depth_loss', 'checkpoint', 'urdf'}:
                continue
            try:
                vals[kw.arg] = ast.literal_eval(kw.value)
            except (ValueError, TypeError, SyntaxError):
                vals[kw.arg] = ast.unparse(kw.value)
    return vals


def audit(workspace):
    workspace = Path(workspace).resolve()
    report = {'source_checkouts': {}, 'not_ready': [], 'source_inspection_required': [], 'interface_hints': {}}
    for name, paths in REQUIRED.items():
        root = workspace / 'src' / name
        exists = root.is_dir()
        rev = git_rev(root) if exists else None
        missing = [p for p in paths if not (root / p).exists()] if exists else paths
        report['source_checkouts'][name] = {'exists': exists, 'commit': rev, 'missing_paths': missing}
        if not exists:
            report['not_ready'].append(f'{name}: checkout not yet cloned')
        elif missing:
            report['not_ready'].append(f'{name}: {len(missing)} expected paths absent; inspect selected version')
    sem = workspace / 'src/RoboOrchardLab'
    rob = workspace / 'src/RoboTwin'
    report['interface_hints']['sem_config'] = config_constants(sem / 'projects/sem/robotwin/config_sem_robotwin.py')
    if rob.is_dir():
        rev = report['source_checkouts']['RoboTwin']['commit']
        if rev != PIN:
            report['not_ready'].append(f'RoboTwin commit mismatch: {rev} != {PIN}')
        ep = rob / 'script/eval_policy.py'
        if ep.is_file():
            src = ep.read_text(encoding='utf-8', errors='replace')
            matches = [ {'line': n, 'snippet': line.strip()[:250]} for n, line in enumerate(src.splitlines(), 1) if 'expert_data_num' in line or re.search(r'test_num\s*=', line)]
            report['interface_hints']['eval_parameters'] = matches[:50]
        cp = rob / 'collect_data.sh'
        if cp.is_file():
            report['interface_hints']['collect_data_sh_preview'] = cp.read_text(encoding='utf-8', errors='replace').splitlines()[:30]
    report['source_inspection_required'] = [
        'Confirm RoboOrchardLab commit compatibility and required installation steps',
        'Inspect the RoboTwin collect_data.sh CLI and depth-enabled YAML',
        'Inspect robotwin_packer.py arguments and actual input HDF5 structure',
        'Inspect train.py --config options and checkpoint/processor outputs',
        'Read script/eval_policy.py and verify expert_data_num meaning and evaluation episode count',
        'Inspect URDF vs robot embodiment, mesh path and kinematics indices',
    ]
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', default='.')
    p.add_argument('--output', default='reports/source_revisions.json')
    a = p.parse_args()
    r = audit(a.workspace)
    out = Path(a.workspace) / a.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print(f'Wrote: {out}')
    if r['not_ready']:
        print('STATUS: NOT_READY (source checkout/inspection needs attention)')
    else:
        print('STATUS: Source paths present; manual compatibility inspection is still required')


if __name__ == '__main__':
    main()
