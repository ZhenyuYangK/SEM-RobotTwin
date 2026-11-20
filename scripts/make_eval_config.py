#!/usr/bin/env python3
"""Generate teacher-style evaluation configuration drafts; never launches evaluation."""
import argparse
import json
import re
from pathlib import Path

SAFE_NAME = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')


def create_files(task, checkpoint, config_file, expert_data_num, template_dir):
    if not SAFE_NAME.fullmatch(task):
        raise ValueError('Unsafe task name')
    if expert_data_num < 1:
        raise ValueError('expert_data_num must be a positive integer')
    for label, value in [('checkpoint', checkpoint), ('config_file', config_file)]:
        if not value or any(c in value for c in '\r\n"\x00'):
            raise ValueError(f'Invalid {label} string')
    yml = (template_dir / 'deploy_policy.yml.template').read_text(encoding='utf-8')
    sh = (template_dir / 'eval.sh.template').read_text(encoding='utf-8')
    yml = yml.replace('@@CHECKPOINT@@', checkpoint).replace('@@CONFIG_FILE@@', config_file)
    sh = sh.replace('@@TASK@@', task).replace('@@EXPERT_DATA_NUM@@', str(expert_data_num))
    return yml, sh


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--task', required=True)
    p.add_argument('--checkpoint', required=True, help='Relative to sem_policy as expected by loader, verify!')
    p.add_argument('--config-file', default='config_sem_robotwin.py')
    p.add_argument('--expert-data-num', type=int, default=5, help='Teacher example: 5; source meaning requires verification')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    yml, sh = create_files(a.task, a.checkpoint, a.config_file, a.expert_data_num, root / 'templates')
    dest = Path(a.out)
    dest.mkdir(parents=True, exist_ok=True)
    for name, content in [('deploy_policy.yml', yml), ('eval.sh', sh)]:
        path = dest / name
        if path.exists():
            raise SystemExit(f'Refusing to overwrite: {path}')
        path.write_text(content, encoding='utf-8')
    (dest / 'REVIEW_REQUIRED.txt').write_text('Draft only. Place under RoboTwin/policy/sem_policy after verifying checkpoint path, config, URDF, depth and current eval source. Do not run blindly.\n', encoding='utf-8')
    print(f'Created evaluation drafts in {dest}. NOT DEPLOYED; inspect first.')


if __name__ == '__main__':
    main()
