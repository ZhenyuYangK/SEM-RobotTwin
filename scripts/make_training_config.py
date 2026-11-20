#!/usr/bin/env python3
"""Generate a single-task SEM training config from pinned source, preserving its other code."""
import argparse
import ast
import shlex
from pathlib import Path

from audit_sources import config_constants, require_locked_files
from discover_tasks import require_locked_task

CONFIG_PATH = 'projects/sem/robotwin/config_sem_robotwin.py'
TRAIN_PATH = 'projects/sem/robotwin/train.py'


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
    p.add_argument('--urdf', type=Path, required=True, help='Verified kinematics URDF on the runtime machine')
    p.add_argument('--pretrained-checkpoint', type=Path, help='Local renamed GroundingDINO checkpoint')
    p.add_argument('--bert-checkpoint', type=Path, help='Local BERT model and tokenizer directory')
    p.add_argument('--training-workspace', type=Path, help='Cloud output directory for train.py --workspace')
    p.add_argument('--max-step', type=int, default=1000)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.max_step <= 0 or a.out.suffix != '.py':
        p.error('Use positive max-step and an output ending in .py')
    try:
        robotwin = require_locked_task(a.workspace, a.task)
        sem = require_locked_files(a.workspace, 'RoboOrchardLab', CONFIG_PATH, TRAIN_PATH)
        target = a.out.resolve()
        if any(target.is_relative_to(root) for root in (robotwin, sem)):
            raise ValueError('Stage the config outside the upstream checkouts')
        source = sem / CONFIG_PATH
        defaults = config_constants(source)
        overrides = {
            'task_names': [a.task], 'multi_task': False, 'max_step': a.max_step,
            'with_depth': True, 'with_depth_loss': True,
            'save_step_freq': min(a.max_step, defaults['save_step_freq']),
            'data_path': str(Path(a.data_path).resolve()), 'urdf': str(a.urdf.resolve()),
        }
        if a.pretrained_checkpoint:
            overrides['checkpoint'] = str(a.pretrained_checkpoint.resolve())
        if a.bert_checkpoint:
            overrides['bert_checkpoint'] = str(a.bert_checkpoint.resolve())
        result = write_config(source.read_text(encoding='utf-8'), overrides)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as handle:
            handle.write(result)
    except (OSError, ValueError) as error:
        p.error(str(error))
    print(f'Staged single-task configuration: {target}')
    print('Check the real LMDB, URDF/joint mapping and pretrained checkpoint on the runtime machine.')
    if a.training_workspace:
        print('Cloud command from RoboOrchardLab/projects/sem/robotwin: ' + shlex.join([
            'python3', 'train.py', '--workspace', str(a.training_workspace.resolve()), '--config', str(target),
        ]))


if __name__ == '__main__':
    main()
