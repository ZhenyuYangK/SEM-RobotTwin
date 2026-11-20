#!/usr/bin/env python3
"""Stage a depth-enabled demo_clean.yml and print the pinned collection command."""
import argparse
import re
import shlex
from pathlib import Path

from discover_tasks import require_locked_task

CONFIG_PATH = 'task_config/demo_clean.yml'


def collection_config(source, episodes):
    if episodes < 1:
        raise ValueError('episodes must be positive')
    expected = ('save_path: ./data', '  rgb: true', '  qpos: true',
                '  collect_head_camera: true', 'collect_data: true')
    if not set(expected).issubset(source.splitlines()):
        raise ValueError('Locked demo_clean no longer matches the SEM collection contract')
    for key, indent, value in [('episode_num', '', episodes),
                               ('depth', '  ', 'true'), ('endpose', '  ', 'true')]:
        pattern = rf'(?m)^{indent}{key}: [^\n]+$'
        source, matches = re.subn(pattern, f'{indent}{key}: {value}', source)
        if matches != 1:
            raise ValueError(f'Expected one field {key!r} in demo_clean')
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--task', required=True)
    parser.add_argument('--episodes', type=int, required=True)
    parser.add_argument('--gpu-id', type=int, default=0)
    parser.add_argument('--out', type=Path, required=True, help='Staging path named demo_clean.yml')
    args = parser.parse_args()
    if args.gpu_id < 0 or args.out.name != 'demo_clean.yml':
        parser.error('Use a nonnegative GPU index and a staging file named demo_clean.yml')
    try:
        root = require_locked_task(args.workspace, args.task, 'collect_data.sh',
                                   'script/collect_data.py', CONFIG_PATH)
        if args.out.resolve().is_relative_to(root):
            raise ValueError('Stage the config outside the upstream checkout')
        source = (root / CONFIG_PATH).read_text(encoding='utf-8')
        config = collection_config(source, args.episodes)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x', encoding='utf-8') as handle:
            handle.write(config)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f'Staged {args.out}. Apply to task_config/demo_clean.yml in an isolated cloud checkout.')
    print('Map RoboTwin/data to the data disk and use an isolated output directory for the smoke run.')
    print('Cloud command from RoboTwin root: ' + shlex.join(
        ['bash', 'collect_data.sh', args.task, 'demo_clean', str(args.gpu_id)]))


if __name__ == '__main__':
    main()
