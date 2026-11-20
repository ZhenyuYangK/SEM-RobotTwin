#!/usr/bin/env python3
"""Find potential RoboTwin task names from the checked-out envs directory; require source validation."""
import argparse
import json
from pathlib import Path


def find_tasks(robotwin):
    envs = Path(robotwin) / 'envs'
    if not envs.is_dir():
        return []
    # In pinned RoboTwin, Python task modules are normally envs/<task_name>.py.
    # Subdirectories are considered only if they contain task Python modules.
    return sorted({p.stem for p in envs.rglob('*.py') if p.name != '__init__.py' and not p.name.startswith('_') and p.parent == envs})


def validate_config(workspace, cfg):
    source_names = set(find_tasks(Path(workspace) / 'src/RoboTwin'))
    selected = [t for t in cfg['tasks'] if t.get('include', False)]
    problems = []
    if not source_names:
        problems.append('No verified source tasks: clone pinned RoboTwin first.')
    if not selected:
        problems.append('No tasks included.')
    for entry in selected:
        name = entry.get('name', '')
        if not isinstance(name, str) or not name or '/' in name or '\\' in name:
            problems.append(f'Invalid task name: {name!r}')
            continue
        if name not in source_names:
            problems.append(f'Task not found in pinned RoboTwin/envs: {name}')
        if entry.get('status') != 'verified_in_pinned_source':
            problems.append(f'Task not marked verified_in_pinned_source: {name}')
    if len({e['name'] for e in selected}) != len(selected):
        problems.append('Repeated selected task names')
    return problems, len(source_names), len(selected)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', default='.')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--list', action='store_true')
    group.add_argument('--validate', action='store_true')
    a = p.parse_args()
    root = Path(a.workspace)
    if a.list:
        found = find_tasks(root / 'src/RoboTwin')
        print(f'Found {len(found)} envs/<task>.py candidates; confirm with task code before selecting:')
        print('\n'.join(found) if found else '(none; clone RoboTwin first)')
        return
    config = json.loads((root / 'configs/project.json').read_text(encoding='utf-8'))
    issues, available, selected = validate_config(root, config)
    print(f'Available: {available}, selected: {selected}')
    if issues:
        for issue in issues:
            print('CHECK:', issue)
        raise SystemExit(1)
    print('Task source checks: PASS. Expert/demo support still needs manual inspection.')


if __name__ == '__main__':
    main()
