#!/usr/bin/env python3
"""Generate a single-task SEM training config from pinned source, preserving its other code."""
import argparse
import ast
import json
from pathlib import Path

from make_eval_config import SAFE_NAME


def write_config(source, overrides):
    """Patch only specified values of the top-level config=dict(...) AST call.

    This does not execute config (avoids model import/GPU side effects).
    """
    tree = ast.parse(source)
    top = next((n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'config' for t in n.targets)), None)
    if top is None or not isinstance(top.value, ast.Call) or not isinstance(top.value.func, ast.Name) or top.value.func.id != 'dict':
        raise ValueError('Cannot find supported top-level config=dict(...)')
    keywords = {kw.arg: kw for kw in top.value.keywords if kw.arg}
    missing = set(overrides) - set(keywords)
    if missing:
        raise ValueError(f'SEM config differs from expected interface; missing keys: {sorted(missing)}')
    lines = source.splitlines(keepends=True)
    def position(row, column):
        # AST col_offset/end_col_offset are UTF-8 byte offsets.
        return sum(len(line.encode('utf-8')) for line in lines[:row-1]) + column
    raw = source.encode('utf-8')
    changes = []
    for key, value in overrides.items():
        node = keywords[key].value
        changes.append((position(node.lineno, node.col_offset), position(node.end_lineno, node.end_col_offset), repr(value).encode('utf-8')))
    for start, end, replacement in sorted(changes, reverse=True):
        raw = raw[:start] + replacement + raw[end:]
    patched = raw.decode('utf-8')
    ast.parse(patched)  # fail early if source changes break parse
    return patched


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', default='.')
    p.add_argument('--task', required=True)
    p.add_argument('--data-path', required=True, help='LMDB directory. Must be confirmed by packer')
    p.add_argument('--urdf', required=True, help='Path to teacher URDF or verified copy on target machine')
    p.add_argument('--max-step', type=int, default=1000)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    if not SAFE_NAME.fullmatch(a.task) or a.max_step <= 0:
        p.error('Invalid task or max-step')
    source = Path(a.workspace) / 'src/RoboOrchardLab/projects/sem/robotwin/config_sem_robotwin.py'
    if not source.is_file():
        p.error(f'SEM source config missing: {source}. Clone the source first.')
    target = Path(a.out)
    if target.exists():
        p.error(f'Refusing to overwrite {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding='utf-8')
    result = write_config(text, {
        'task_names': [a.task], 'multi_task': False, 'max_step': a.max_step,
        'data_path': a.data_path, 'urdf': a.urdf,
    })
    target.write_text(result, encoding='utf-8')
    print(f'Generated review-required training config: {target}')
    print('Check pretrained weights, robot joint mapping, depth, data path and actual train.py --config semantics.')


if __name__ == '__main__':
    main()
