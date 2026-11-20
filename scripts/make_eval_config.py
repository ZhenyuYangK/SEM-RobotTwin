#!/usr/bin/env python3
"""Generate teacher-style evaluation configuration drafts; never launches evaluation."""
import argparse
import json
import re
from pathlib import Path

from audit_sources import require_locked_files
from discover_tasks import SAFE_NAME, require_locked_task

POLICY = 'projects/sem/robotwin/sem_policy'


def create_files(task, checkpoint, config_file, expert_data_num, template_dir):
    if not SAFE_NAME.fullmatch(task):
        raise ValueError('Unsafe task name')
    if expert_data_num < 1:
        raise ValueError('expert_data_num must be a positive integer')
    for label, value in [('checkpoint', checkpoint), ('config_file', config_file)]:
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError(f'Invalid {label} string')
    if not config_file.endswith('.py'):
        raise ValueError('config_file must end in .py')
    yml = (template_dir / 'deploy_policy.yml.template').read_text(encoding='utf-8')
    sh = (template_dir / 'eval.sh.template').read_text(encoding='utf-8')
    values = {'@@CHECKPOINT@@': json.dumps(checkpoint, ensure_ascii=False),
              '@@CONFIG_FILE@@': json.dumps(config_file, ensure_ascii=False)}
    yml = re.sub(r'@@(?:CHECKPOINT|CONFIG_FILE)@@', lambda match: values[match[0]], yml)
    sh = sh.replace('@@TASK@@', task).replace('@@EXPERT_DATA_NUM@@', str(expert_data_num))
    return yml, sh


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', default='.')
    p.add_argument('--task', required=True)
    p.add_argument('--checkpoint', required=True, help='Absolute runtime path or relative to the deployed sem_policy directory')
    p.add_argument('--config-file', default='config_sem_robotwin.py')
    p.add_argument('--expert-data-num', type=int, required=True, help='Training demonstration count recorded by the teacher workflow')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    created = []
    try:
        robotwin = require_locked_task(a.workspace, a.task, 'script/eval_policy.py')
        sem = require_locked_files(a.workspace, 'RoboOrchardLab', f'{POLICY}/deploy_policy.py',
                                   f'{POLICY}/deploy_policy.yml', f'{POLICY}/eval.sh')
        dest = Path(a.out).resolve()
        if any(dest.is_relative_to(path) for path in (robotwin, sem)):
            raise ValueError('Stage the policy configuration outside the upstream checkouts')
        yml, script = create_files(a.task, a.checkpoint, a.config_file, a.expert_data_num, root / 'templates')
        dest.mkdir(parents=True, exist_ok=True)
        for name, content in [('deploy_policy.yml', yml), ('eval.sh', script)]:
            path = dest / name
            with path.open('x', encoding='utf-8') as handle:
                created.append(path)
                handle.write(content)
    except (OSError, ValueError) as error:
        for path in created:
            path.unlink()
        p.error(str(error))
    print(f'Staged evaluation configuration and launcher in {dest}')
    print('Apply after checking checkpoint, config and depth in the cloud. Fixed evaluation uses 100 valid episodes.')


if __name__ == '__main__':
    main()
