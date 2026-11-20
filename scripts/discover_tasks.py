#!/usr/bin/env python3
"""Find potential RoboTwin task names from the checked-out envs directory; require source validation."""
import argparse
import ast
import re
import json
from pathlib import Path

from audit_sources import PIN, git_rev, require_locked_files

SAFE_NAME = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*")
TASK_METHODS = {"setup_demo", "play_once", "check_success"}


def has_task_interface(robotwin, name):
    task = robotwin / 'envs' / f'{name}.py'
    instruction = robotwin / 'description/task_instruction' / f'{name}.json'
    if not task.is_file() or not instruction.is_file():
        return False
    tree = ast.parse(task.read_text(encoding='utf-8'))
    prompts = json.loads(instruction.read_text(encoding='utf-8'))
    return bool(prompts.get('seen') and prompts.get('unseen') and any(
        isinstance(node, ast.ClassDef) and node.name == name
        and TASK_METHODS.issubset({child.name for child in node.body if isinstance(child, ast.FunctionDef)})
        for node in tree.body
    ))


def find_tasks(robotwin):
    robotwin = Path(robotwin)
    return sorted(path.stem for path in (robotwin / 'envs').glob('*.py')
                  if SAFE_NAME.fullmatch(path.stem) and has_task_interface(robotwin, path.stem))


def require_locked_task(workspace, name, *paths):
    if not SAFE_NAME.fullmatch(name):
        raise ValueError(f'Invalid task name: {name!r}')
    root = require_locked_files(workspace, 'RoboTwin', f'envs/{name}.py',
                                f'description/task_instruction/{name}.json', *paths)
    if not has_task_interface(root, name):
        raise ValueError(f'Task interface incomplete: {name}')
    return root


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
        if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
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
    if git_rev(root / 'src/RoboTwin') != PIN:
        p.error(f'RoboTwin must be checked out at {PIN}')
    if a.list:
        found = find_tasks(root / 'src/RoboTwin')
        print(f'Found {len(found)} task modules with expert/success methods and seen/unseen prompts:')
        print('\n'.join(found) if found else '(none; clone RoboTwin first)')
        return
    config = json.loads((root / 'configs/project.json').read_text(encoding='utf-8'))
    issues, available, selected = validate_config(root, config)
    print(f'Available: {available}, selected: {selected}')
    if not issues:
        for task in config['tasks']:
            if task.get('include'):
                try:
                    require_locked_task(root, task['name'])
                except ValueError as error:
                    issues.append(str(error))
    if issues:
        for issue in issues:
            print('CHECK:', issue)
        raise SystemExit(1)
    print('Task source checks: PASS. Simulation remains a separate check.')


if __name__ == '__main__':
    main()
